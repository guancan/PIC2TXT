"""
小红书笔记处理服务
提供小红书笔记数据的解析、处理和管理功能

职责:
1. 笔记级别操作：负责解析单个笔记的数据结构
2. 资源提取：从笔记中提取图片链接和视频链接
3. 任务创建：为图片和视频创建OCR和字幕提取任务
4. 关联管理：维护笔记与任务的关联关系
5. 结果汇总：汇总同一笔记的多个处理结果

与CSVService的关系:
- XHSNoteService是更底层的服务，负责笔记级别的操作
- XHSNoteService被CSVService调用，处理单个笔记数据
- XHSNoteService将处理结果返回给CSVService，由CSVService回写到CSV文件
"""

import os
import json
import logging
import traceback
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import threading

from database.db_manager import DatabaseManager
from services.task_service import TaskService
from utils.csv_utils import extract_image_urls
import config
from utils.video_utils import is_valid_video_url
from database.models import TASK_TYPE_VIDEO, VIDEO_ENGINE_ALI_PARAFORMER

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加图片URL验证函数
def is_valid_image_url(url):
    """
    检查URL是否为有效的图片URL
    
    参数:
        url (str): 要检查的URL
        
    返回:
        bool: 是否为有效的图片URL
    """
    if not url:
        return False
    
    # 简单验证URL格式
    url = url.lower().strip()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    
    # 检查URL是否以有效的图片扩展名结尾
    has_valid_extension = any(url.endswith(ext) for ext in valid_extensions)
    
    # 小红书图片URL可能不带扩展名，但通常包含特定的域名
    is_xhs_image = 'xhscdn.com' in url or 'xiaohongshu.com' in url
    
    return has_valid_extension or is_xhs_image

class XHSNoteService:
    """小红书笔记处理服务类"""
    
    def __init__(self, db_manager=None, task_service=None):
        """
        初始化小红书笔记服务
        
        参数:
            db_manager: 数据库管理器实例
            task_service: 任务服务实例
        """
        self.db_manager = db_manager or DatabaseManager(config.DB_PATH)
        self.task_service = task_service or TaskService()
    
    def process_note(self, note_data, ocr_engine="mistral", process_video=False, video_engine=VIDEO_ENGINE_ALI_PARAFORMER):
        """
        处理单个笔记数据，提取图片和视频并创建处理任务
        
        参数:
            note_data (dict): 笔记数据，包含note_url, image_list, video_url等字段
            ocr_engine (str): OCR引擎类型
            process_video (bool): 是否处理视频
            video_engine (str): 视频处理引擎类型
            
        返回:
            Tuple[bool, str, List[int]]: (是否成功, 消息, 任务ID列表)
        """
        try:
            note_url = note_data.get("note_url")
            if not note_url:
                return False, "笔记URL为空", []
            
            # 标准化笔记URL
            note_url = self._normalize_note_url(note_url)
            
            # 获取图片列表和视频URL
            image_list = note_data.get("image_list", "")
            video_url = note_data.get("video_url", "")
            
            # 提取图片URL
            image_urls = extract_image_urls(image_list)
            
            # 创建任务列表
            task_ids = []
            image_task_ids = []
            video_task_ids = []
            
            # 创建图片任务
            if image_urls:
                for image_url in image_urls:
                    if is_valid_image_url(image_url):
                        task_id = self.task_service.create_task(url=image_url, ocr_engine=ocr_engine)
                        image_task_ids.append(task_id)
                        task_ids.append(task_id)
            
            # 创建视频任务
            if process_video and video_url and is_valid_video_url(video_url):
                video_task_id = self.task_service.create_video_task(url=video_url, video_engine=video_engine)
                video_task_ids.append(video_task_id)
                task_ids.append(video_task_id)
            
            # 保存笔记与任务的关联关系
            if task_ids:
                self._save_note_task_relation(note_url, image_task_ids, video_task_ids)
            
            # 返回结果
            return True, f"成功创建 {len(task_ids)} 个任务（图片：{len(image_task_ids)}，视频：{len(video_task_ids)}）", task_ids
            
        except Exception as e:
            logger.error(f"处理笔记数据时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"处理笔记数据时出错: {str(e)}", []
    
    def get_note_ocr_results(self, note_url):
        """
        获取笔记的OCR结果
        
        参数:
            note_url (str): 笔记URL
            
        返回:
            str: 合并后的OCR结果文本
        """
        try:
            # 获取笔记关联的任务ID
            relation = self.db_manager.execute_query(
                """
                SELECT task_ids FROM note_task_relations 
                WHERE note_url = ?
                """,
                (note_url,)
            )
            
            if not relation:
                logger.warning(f"找不到笔记关联记录: {note_url}")
                return ""
            
            # 解析任务ID列表
            try:
                task_ids = json.loads(relation[0]["task_ids"])
            except (json.JSONDecodeError, KeyError):
                logger.error(f"解析任务ID列表失败: {relation[0]['task_ids']}")
                return ""
            
            # 获取所有任务的结果
            all_results = []
            for i, task_id in enumerate(task_ids):
                result = self.task_service.get_task_result(task_id)
                if result and "text_content" in result:
                    # 添加图片序号标记
                    image_index = i + 1
                    marked_result = f"【图片{image_index}内容解析】\n{result['text_content']}"
                    all_results.append(marked_result)
            
            # 合并结果
            return "\n\n".join(all_results)
        except Exception as e:
            logger.error(f"获取笔记OCR结果时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return ""
    
    def get_note_video_results(self, note_url: str) -> str:
        """
        获取笔记的视频处理结果
        
        参数:
            note_url (str): 笔记URL
            
        返回:
            str: 视频处理结果文本
        """
        try:
            # 获取笔记关联的视频任务ID
            relation = self.db_manager.execute_query(
                """
                SELECT video_task_ids FROM note_task_relations 
                WHERE note_url = ?
                """,
                (note_url,)
            )
            
            if not relation:
                logger.warning(f"找不到笔记关联记录: {note_url}")
                return ""
            
            # 解析视频任务ID列表
            try:
                video_task_ids = json.loads(relation[0]["video_task_ids"])
            except (json.JSONDecodeError, TypeError):
                logger.error(f"解析视频任务ID列表失败: {relation[0]['video_task_ids']}")
                return ""
            
            # 获取所有视频任务的结果
            all_results = []
            for i, task_id in enumerate(video_task_ids):
                result = self.task_service.get_task_result(task_id)
                if result and "text_content" in result:
                    # 添加视频序号标记
                    video_index = i + 1
                    marked_result = f"【视频语音字幕解析{video_index}】\n{result['text_content']}"
                    all_results.append(marked_result)
            
            # 合并结果
            return "\n\n".join(all_results)
        except Exception as e:
            logger.error(f"获取笔记视频结果时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return ""
    
    def get_note_all_results(self, note_url: str) -> Tuple[bool, str, str]:
        """
        获取笔记的所有处理结果（包括OCR和视频）
        
        参数:
            note_url (str): 笔记URL
            
        返回:
            Tuple[bool, str, str]: (是否成功, 消息, 合并后的结果文本)
        """
        try:
            # 获取OCR结果
            ocr_text = self.get_note_ocr_results(note_url)
            
            # 获取视频处理结果
            video_text = self.get_note_video_results(note_url)
            
            # 合并结果
            results = []
            if ocr_text:
                results.append(ocr_text)
            if video_text:
                results.append(video_text)
            
            if not results:
                return False, "笔记没有处理结果", ""
            
            # 合并所有结果，每个结果之间添加分隔线
            combined_text = "\n\n" + "-" * 40 + "\n\n".join(results)
            return True, "成功获取处理结果", combined_text
        except Exception as e:
            logger.error(f"获取笔记所有处理结果时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"获取笔记所有处理结果时出错: {str(e)}", ""
    
    def _create_note_relation(self, note_url: str) -> int:
        """
        创建笔记-任务关联记录
        
        参数:
            note_url (str): 笔记URL
            
        返回:
            int: 关联记录ID
        """
        try:
            # 检查是否已存在相同URL的关联记录
            existing_relation = self.db_manager.execute_query(
                "SELECT id FROM note_task_relations WHERE note_url = ?",
                (note_url,)
            )
            
            if existing_relation:
                return existing_relation[0]["id"]
            
            # 创建新关联记录
            relation_id = self.db_manager.execute_query(
                """
                INSERT INTO note_task_relations (note_url, task_ids, video_task_ids, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (note_url, "[]", "[]", "pending", datetime.now().isoformat(), datetime.now().isoformat())
            )[0]["id"]
            
            return relation_id
        except Exception as e:
            logger.error(f"创建笔记关联记录时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return -1
        
    def _update_note_relation(self, relation_id: int, task_ids: List[int], video_task_ids: List[int] = None) -> bool:
        """
        更新笔记-任务关联记录
        
        参数:
            relation_id (int): 关联记录ID
            task_ids (List[int]): 任务ID列表
            video_task_ids (List[int], optional): 视频任务ID列表
            
        返回:
            bool: 更新是否成功
        """
        try:
            # 获取现有关联记录
            relation = self.db_manager.execute_query(
                "SELECT task_ids, video_task_ids FROM note_task_relations WHERE id = ?",
                (relation_id,)
            )
            
            if not relation:
                logger.error(f"找不到关联记录: {relation_id}")
                return False
            
            # 合并任务ID
            existing_task_ids = json.loads(relation[0]["task_ids"]) if relation[0]["task_ids"] else []
            all_task_ids = list(set(existing_task_ids + task_ids))
            
            # 合并视频任务ID
            existing_video_task_ids = json.loads(relation[0]["video_task_ids"]) if relation[0].get("video_task_ids") else []
            all_video_task_ids = list(set(existing_video_task_ids + (video_task_ids or [])))
            
            # 更新关联记录
            self.db_manager.execute_query(
                """
                UPDATE note_task_relations 
                SET task_ids = ?, video_task_ids = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(all_task_ids), json.dumps(all_video_task_ids), "processing", datetime.now().isoformat(), relation_id)
            )
            
            return True
        except Exception as e:
            logger.error(f"更新笔记关联记录时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _get_note_relation(self, note_url: str) -> Optional[Dict[str, Any]]:
        """
        获取笔记-任务关联记录
        
        参数:
            note_url (str): 笔记URL
            
        返回:
            Optional[Dict[str, Any]]: 关联记录
        """
        try:
            relation = self.db_manager.execute_query(
                "SELECT * FROM note_task_relations WHERE note_url = ?",
                (note_url,)
            )
            
            return relation[0] if relation else None
        except Exception as e:
            logger.error(f"获取笔记关联记录时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def _get_or_create_note_relation(self, note_url: str) -> int:
        """
        获取笔记-任务关联记录，如果不存在则创建
        
        参数:
            note_url (str): 笔记URL
            
        返回:
            int: 关联记录ID
        """
        try:
            # 检查是否已存在相同URL的关联记录
            existing_relation = self.db_manager.execute_query(
                "SELECT id FROM note_task_relations WHERE note_url = ?",
                (note_url,)
            )
            
            if existing_relation:
                return existing_relation[0]["id"]
            
            # 创建新关联记录
            relation_id = self.db_manager.execute_query(
                """
                INSERT INTO note_task_relations (note_url, task_ids, video_task_ids, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (note_url, "[]", "[]", "pending", datetime.now().isoformat(), datetime.now().isoformat())
            )[0]["id"]
            
            return relation_id
        except Exception as e:
            logger.error(f"获取笔记关联记录时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return -1

    def _save_note_task_relation(self, note_url, image_task_ids, video_task_ids):
        """
        保存笔记与任务的关联关系
        
        参数:
            note_url (str): 笔记URL
            image_task_ids (list): 图片任务ID列表
            video_task_ids (list): 视频任务ID列表
            
        返回:
            int: 关联记录ID，失败返回-1
        """
        try:
            # 将任务ID列表转换为JSON字符串
            image_task_ids_json = json.dumps(image_task_ids)
            video_task_ids_json = json.dumps(video_task_ids)
            
            # 检查是否已存在关联记录
            relation_id = self.get_note_relation_id(note_url)
            
            if relation_id > 0:
                # 更新现有记录
                self.db_manager.execute_query(
                    """
                    UPDATE note_task_relations 
                    SET task_ids = ?, video_task_ids = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (image_task_ids_json, video_task_ids_json, datetime.now().isoformat(), relation_id)
                )
                logger.info(f"更新笔记关联记录 ID: {relation_id}, 笔记: {note_url}")
            else:
                # 创建新记录
                result = self.db_manager.execute_query(
                    """
                    INSERT INTO note_task_relations (note_url, task_ids, video_task_ids, status)
                    VALUES (?, ?, ?, 'pending')
                    RETURNING id
                    """,
                    (note_url, image_task_ids_json, video_task_ids_json)
                )
                relation_id = result[0]["id"] if result else -1
                logger.info(f"创建笔记关联记录 ID: {relation_id}, 笔记: {note_url}")
            
            return relation_id
        except Exception as e:
            logger.error(f"保存笔记关联记录时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return -1

    def get_note_relation_id(self, note_url):
        """
        获取笔记关联记录ID
        
        参数:
            note_url (str): 笔记URL
            
        返回:
            int: 关联记录ID，如果不存在则返回-1
        """
        try:
            # 查询数据库获取关联记录ID
            result = self.db_manager.execute_query(
                """
                SELECT id FROM note_task_relations 
                WHERE note_url = ?
                """,
                (note_url,)
            )
            
            return result[0]["id"] if result else -1
        except Exception as e:
            logger.error(f"获取笔记关联记录ID时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return -1

    def _normalize_note_url(self, url):
        """
        标准化笔记URL，移除不必要的参数
        
        参数:
            url (str): 原始笔记URL
            
        返回:
            str: 标准化后的URL
        """
        if not url:
            return ""
        
        # 移除URL中的查询参数
        import re
        from urllib.parse import urlparse, urlunparse
        
        parsed = urlparse(url)
        path = parsed.path
        
        # 提取笔记ID
        note_id_match = re.search(r'/explore/([a-zA-Z0-9]+)', path)
        if note_id_match:
            note_id = note_id_match.group(1)
            # 构建标准URL
            return f"https://www.xiaohongshu.com/explore/{note_id}"
        
        return url 