"""
小红书笔记处理服务
提供小红书笔记数据的解析、处理和管理功能
"""

import os
import json
import logging
import traceback
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from database.db_manager import DatabaseManager
from services.task_service import TaskService
from utils.csv_utils import extract_image_urls
import config
from utils.video_utils import is_valid_video_url
from database.models import TASK_TYPE_VIDEO, VIDEO_ENGINE_ALI_PARAFORMER

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    
    def process_note(self, note_data: Dict[str, Any], ocr_engine: str = "mistral", process_video: bool = False, video_engine: str = VIDEO_ENGINE_ALI_PARAFORMER) -> Tuple[bool, str, List[int]]:
        """
        处理单个小红书笔记数据
        
        参数:
            note_data (Dict[str, Any]): 笔记数据字典
            ocr_engine (str): OCR引擎类型
            process_video (bool): 是否处理视频
            video_engine (str): 视频处理引擎类型
            
        返回:
            Tuple[bool, str, List[int]]: (是否成功, 消息, 任务ID列表)
        """
        try:
            # 提取笔记URL和图片列表
            note_url = note_data.get("note_url")
            if not note_url:
                return False, "笔记URL不能为空", []
            
            # 为笔记创建关联记录
            relation_id = self._create_note_relation(note_url)
            if relation_id < 0:
                return False, "创建笔记关联记录失败", []
            
            task_ids = []
            
            # 处理图片
            image_list_str = note_data.get("image_list", "")
            image_urls = extract_image_urls(image_list_str)
            if image_urls:
                # 为每个图片URL创建任务
                for img_url in image_urls:
                    task_id = self.task_service.create_task(url=img_url, ocr_engine=ocr_engine)
                    if task_id > 0:
                        task_ids.append(task_id)
            
            # 处理视频
            video_task_ids = []
            if process_video:
                # 检查笔记URL是否可能是视频URL
                if is_valid_video_url(note_url):
                    # 创建视频任务
                    video_task_id = self.task_service.create_task(
                        url=note_url, 
                        ocr_engine=None,
                        task_type=TASK_TYPE_VIDEO,
                        video_engine=video_engine
                    )
                    if video_task_id > 0:
                        video_task_ids.append(video_task_id)
                
                # 检查是否有视频URL字段
                video_url = note_data.get("video_url", "")
                if video_url and is_valid_video_url(video_url):
                    video_task_id = self.task_service.create_task(
                        url=video_url, 
                        ocr_engine=None,
                        task_type=TASK_TYPE_VIDEO,
                        video_engine=video_engine
                    )
                    if video_task_id > 0:
                        video_task_ids.append(video_task_id)
            
            # 如果既没有图片任务也没有视频任务，则返回失败
            if not task_ids and not video_task_ids:
                return False, "没有找到有效的图片或视频URL", []
            
            # 更新笔记关联记录
            success = self._update_note_relation(relation_id, task_ids, video_task_ids)
            if not success:
                return False, "更新笔记关联记录失败", task_ids + video_task_ids
            
            total_tasks = len(task_ids) + len(video_task_ids)
            return True, f"成功创建 {total_tasks} 个任务（图片：{len(task_ids)}，视频：{len(video_task_ids)}）", task_ids + video_task_ids
            
        except Exception as e:
            logger.error(f"处理笔记数据时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"处理笔记数据时出错: {str(e)}", []
    
    def get_note_ocr_results(self, note_url: str) -> str:
        """
        获取笔记的OCR结果
        
        参数:
            note_url (str): 笔记URL
            
        返回:
            str: 合并后的OCR结果文本
        """
        try:
            # 获取笔记关联记录
            relation = self._get_note_relation(note_url)
            if not relation:
                logger.warning(f"找不到笔记关联记录: {note_url}")
                return ""
            
            # 获取任务ID列表
            task_ids = json.loads(relation["task_ids"]) if relation["task_ids"] else []
            if not task_ids:
                logger.warning(f"笔记没有关联任务: {note_url}")
                return ""
            
            # 获取所有任务的OCR结果
            results = []
            for i, task_id in enumerate(task_ids):
                result = self.task_service.get_task_result(task_id)
                if result and result.get("text_content"):
                    # 添加图片标记
                    image_text = f"[图片{i+1}的文本]\n{result['text_content']}\n[图片{i+1}文本结束]"
                    results.append(image_text)
            
            # 合并OCR结果
            if not results:
                logger.warning(f"笔记没有OCR结果: {note_url}")
                return ""
            
            # 合并所有结果，每个结果之间添加换行符
            combined_text = "\n\n".join(results)
            return combined_text
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
            # 获取笔记关联记录
            relation = self._get_note_relation(note_url)
            if not relation:
                logger.warning(f"找不到笔记关联记录: {note_url}")
                return ""
            
            # 获取视频任务ID列表
            video_task_ids = json.loads(relation["video_task_ids"]) if relation.get("video_task_ids") else []
            if not video_task_ids:
                logger.warning(f"笔记没有关联视频任务: {note_url}")
                return ""
            
            # 获取所有视频任务的处理结果
            results = []
            for i, task_id in enumerate(video_task_ids):
                result = self.task_service.get_task_result(task_id)
                if result and result.get("text_content"):
                    # 添加视频标记
                    video_text = f"[视频{i+1}的文本]\n{result['text_content']}\n[视频{i+1}文本结束]"
                    results.append(video_text)
            
            # 合并处理结果
            if not results:
                logger.warning(f"笔记没有视频处理结果: {note_url}")
                return ""
            
            # 合并所有结果，每个结果之间添加换行符
            combined_text = "\n\n".join(results)
            return combined_text
        except Exception as e:
            logger.error(f"获取笔记视频处理结果时出错: {str(e)}")
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