"""
CSV表格处理服务
提供CSV表格的读取、处理和写入功能，支持小红书笔记数据的处理

职责:
1. 文件级别操作：负责CSV文件的读取、验证和写入
2. 批量处理：遍历CSV的每一行数据，调用XHSNoteService处理单个笔记
3. 结果汇总：从XHSNoteService获取处理结果，并回写到CSV文件
4. 数据源管理：注册和管理CSV数据源

与XHSNoteService的关系:
- CSVService是更高层次的服务，负责文件级别的操作
- CSVService调用XHSNoteService处理单个笔记数据
- CSVService从XHSNoteService获取处理结果，并回写到CSV文件
"""

import os
import json
import logging
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Set
import traceback
from datetime import datetime
import concurrent.futures

from utils.csv_utils import read_csv, write_csv, extract_image_urls, validate_csv_structure, add_column_if_not_exists
from database.db_manager import DatabaseManager
from services.task_service import TaskService
from services.xhs_note_service import XHSNoteService
import config
from database.models import VIDEO_ENGINE_ALI_PARAFORMER, TASK_TYPE_IMAGE, TASK_TYPE_VIDEO
from utils.video_utils import is_valid_video_url

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CSVService:
    """CSV表格处理服务类"""
    
    def __init__(self, db_manager=None, task_service=None, note_service=None):
        """
        初始化CSV服务
        
        参数:
            db_manager: 数据库管理器实例
            task_service: 任务服务实例
            note_service: 小红书笔记服务实例
        """
        self.db_manager = db_manager or DatabaseManager(config.DB_PATH)
        self.task_service = task_service or TaskService()
        self.note_service = note_service or XHSNoteService(self.db_manager, self.task_service)
        
        # 确保输出目录存在
        os.makedirs(config.RESULT_DIR, exist_ok=True)
    
    def process_csv_file(self, file_path: str, ocr_engine: str = "mistral", process_video: bool = False, video_engine: str = VIDEO_ENGINE_ALI_PARAFORMER) -> Tuple[bool, str, Optional[str]]:
        """
        处理CSV文件，提取图片链接和视频链接并创建处理任务
        
        参数:
            file_path (str): CSV文件路径
            ocr_engine (str): OCR引擎类型
            process_video (bool): 是否处理视频
            video_engine (str): 视频处理引擎类型
            
        返回:
            Tuple[bool, str, Optional[str]]: (是否成功, 消息, 输出文件路径)
        """
        try:
            # 读取CSV文件
            df = read_csv(file_path)
            if df is None:
                return False, "无法读取CSV文件", None
            
            # 验证CSV结构
            required_fields = ["note_url"]
            is_valid, error_msg = validate_csv_structure(df, required_fields)
            if not is_valid:
                return False, error_msg, None
            
            # 添加image_txt列和video_txt列（如果不存在）
            df = add_column_if_not_exists(df, "image_txt", "")
            if process_video:
                df = add_column_if_not_exists(df, "video_txt", "")
            
            # 记录数据源
            source_id = self._register_data_source(file_path, "csv")
            
            # 处理每一行数据，创建任务
            total_rows = len(df)
            processed_rows = 0
            failed_rows = 0
            all_task_ids = set()  # 收集所有任务ID
            
            for index, row in df.iterrows():
                try:
                    # 获取笔记URL
                    note_url = row.get("note_url")
                    if not note_url:
                        logger.warning(f"行 {index+1} 缺少笔记URL，跳过")
                        failed_rows += 1
                        continue
                    
                    # 构建笔记数据
                    note_data = {
                        "note_url": note_url,
                        "image_list": row.get("image_list", ""),
                        "video_url": row.get("video_url", "")
                    }
                    
                    # 处理笔记数据，创建任务
                    success, message, task_ids = self.note_service.process_note(
                        note_data, 
                        ocr_engine=ocr_engine,
                        process_video=process_video,
                        video_engine=video_engine
                    )
                    
                    if success:
                        processed_rows += 1
                        all_task_ids.update(task_ids)
                        logger.info(f"成功处理行 {index+1}: {message}")
                    else:
                        failed_rows += 1
                        logger.warning(f"处理行 {index+1} 失败: {message}")
                    
                except Exception as e:
                    failed_rows += 1
                    logger.error(f"处理行 {index+1} 时出错: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # 并行处理所有任务
            if all_task_ids:
                self._process_tasks_in_parallel(all_task_ids)
            
            # 更新CSV文件中的处理结果
            updated_rows = self._update_results(df, process_video)
            
            # 生成输出文件路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(
                config.RESULT_DIR, 
                f"processed_{os.path.basename(file_path).split('.')[0]}_{timestamp}.csv"
            )
            
            # 写入CSV文件
            success = write_csv(df, output_file)
            if not success:
                return False, "写入输出CSV文件失败", None
            
            return True, f"成功处理 {processed_rows}/{total_rows} 行，失败 {failed_rows} 行", output_file
            
        except Exception as e:
            logger.error(f"处理CSV文件时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"处理CSV文件时出错: {str(e)}", None
    
    def _process_tasks_in_parallel(self, task_ids: Set[int], max_workers: int = 5):
        """
        并行处理多个任务
        
        参数:
            task_ids (Set[int]): 任务ID集合
            max_workers (int): 最大并行工作线程数
        """
        # 将任务分为图片任务和视频任务
        image_tasks = []
        video_tasks = []
        
        for task_id in task_ids:
            task = self.task_service.get_task(task_id)
            if not task:
                continue
                
            if task.get("task_type") == TASK_TYPE_IMAGE:
                image_tasks.append(task_id)
            elif task.get("task_type") == TASK_TYPE_VIDEO:
                video_tasks.append(task_id)
        
        logger.info(f"开始并行处理 {len(image_tasks)} 个图片任务和 {len(video_tasks)} 个视频任务")
        
        # 使用线程池并行处理任务
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有图片任务
            image_futures = {executor.submit(self.task_service.process_task, task_id): task_id for task_id in image_tasks}
            
            # 提交所有视频任务
            video_futures = {executor.submit(self.task_service.process_video_task, task_id): task_id for task_id in video_tasks}
            
            # 合并所有future
            all_futures = {**image_futures, **video_futures}
            
            # 等待所有任务完成
            for future in concurrent.futures.as_completed(all_futures):
                task_id = all_futures[future]
                try:
                    success = future.result()
                    if success:
                        logger.info(f"任务 {task_id} 处理成功")
                    else:
                        logger.warning(f"任务 {task_id} 处理失败")
                except Exception as e:
                    logger.error(f"处理任务 {task_id} 时出错: {str(e)}")
        
        logger.info(f"所有任务处理完成")
    
    def _update_results(self, df, include_video=False):
        """
        更新CSV中的处理结果
        
        参数:
            df (pandas.DataFrame): 数据框
            include_video (bool): 是否包含视频处理结果
            
        返回:
            int: 更新的行数
        """
        total_rows = len(df)
        updated_rows = 0
        
        for index, row in df.iterrows():
            try:
                note_url = row.get("note_url")
                if not note_url:
                    continue
                
                # 标准化笔记URL
                note_url = self.note_service._normalize_note_url(note_url)
                
                # 获取OCR结果
                ocr_result = self.note_service.get_note_ocr_results(note_url)
                if ocr_result:
                    df.at[index, "image_txt"] = ocr_result
                    updated_rows += 1
                    logger.info(f"已更新行 {index+1} 的OCR结果，长度: {len(ocr_result)}")
                
                # 获取视频处理结果
                if include_video:
                    video_result = self.note_service.get_note_video_results(note_url)
                    if video_result:
                        df.at[index, "video_txt"] = video_result
                        logger.info(f"已更新行 {index+1} 的视频处理结果，长度: {len(video_result)}")
            
            except Exception as e:
                logger.error(f"更新行 {index+1} 的处理结果时出错: {str(e)}")
                logger.error(traceback.format_exc())
        
        logger.info(f"共更新了 {updated_rows}/{total_rows} 行的处理结果")
        return updated_rows
    
    def update_csv_with_results(self, csv_file_path: str, include_video: bool = True, strict_matching: bool = False) -> Tuple[bool, str, str]:
        """
        更新CSV文件，添加处理结果
        
        参数:
            csv_file_path (str): CSV文件路径
            include_video (bool): 是否包含视频处理结果
            strict_matching (bool): 是否使用严格URL匹配
            
        返回:
            Tuple[bool, str, str]: (成功标志, 消息, 输出文件路径)
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(csv_file_path):
                return False, f"文件不存在: {csv_file_path}", ""
            
            # 读取CSV文件
            df = pd.read_csv(csv_file_path)
            
            # 检查是否包含note_url列
            if 'note_url' not in df.columns:
                return False, "CSV文件中缺少note_url列", ""
            
            # 创建XHSNoteService实例
            xhs_note_service = XHSNoteService(db_manager=self.db_manager)
            
            # 添加OCR结果列和视频转写结果列
            if 'ocr_result' not in df.columns:
                df['ocr_result'] = ""
            if 'video_transcript' not in df.columns and include_video:
                df['video_transcript'] = ""
            
            # 遍历每一行，获取处理结果
            updated_count = 0
            for index, row in df.iterrows():
                note_url = row['note_url']
                if pd.isna(note_url) or not note_url:
                    continue
                    
                # 获取笔记处理结果
                # 传递strict_matching参数给get_note_processing_results方法
                results = xhs_note_service.get_note_processing_results(note_url, strict_matching=strict_matching)
                
                if results:
                    # 更新OCR结果
                    if 'ocr_text' in results and results['ocr_text']:
                        df.at[index, 'ocr_result'] = results['ocr_text']
                        updated_count += 1
                    
                    # 更新视频转写结果
                    if include_video and 'video_transcript' in results and results['video_transcript']:
                        df.at[index, 'video_transcript'] = results['video_transcript']
                        updated_count += 1
            
            # 生成输出文件名
            timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
            output_dir = os.path.dirname(csv_file_path)
            base_name = os.path.splitext(os.path.basename(csv_file_path))[0]
            output_file = os.path.join(output_dir, f"{base_name}_{timestamp}_updated.csv")
            
            # 保存更新后的CSV文件
            df.to_csv(output_file, index=False)
            
            return True, f"成功更新了{updated_count}条记录", output_file
        except Exception as e:
            logger.error(f"更新CSV结果时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"更新CSV结果时出错: {str(e)}", ""
    
    def _register_data_source(self, source_path: str, source_type: str = "csv") -> int:
        """
        注册数据源
        
        参数:
            source_path (str): 数据源路径
            source_type (str): 数据源类型
            
        返回:
            int: 数据源ID
        """
        try:
            # 检查是否已存在相同路径的数据源
            existing_source = self.db_manager.execute_query(
                "SELECT id FROM data_sources WHERE source_path = ?",
                (source_path,)
            )
            
            if existing_source:
                return existing_source[0]["id"]
            
            # 创建新数据源记录
            config_json = json.dumps({
                "type": source_type,
                "created_at": datetime.now().isoformat()
            })
            
            source_id = self.db_manager.execute_query(
                """
                INSERT INTO data_sources (source_type, source_path, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                """,
                (source_type, source_path, config_json, datetime.now().isoformat(), datetime.now().isoformat())
            )[0]["id"]
            
            return source_id
        except Exception as e:
            logger.error(f"注册数据源时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return -1 