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
from typing import List, Dict, Any, Optional, Tuple
import traceback
from datetime import datetime

from utils.csv_utils import read_csv, write_csv, extract_image_urls, validate_csv_structure, add_column_if_not_exists
from database.db_manager import DatabaseManager
from services.task_service import TaskService
from services.xhs_note_service import XHSNoteService
import config
from database.models import VIDEO_ENGINE_ALI_PARAFORMER, TASK_TYPE_VIDEO
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
            
            # 处理每一行数据
            total_rows = len(df)
            processed_rows = 0
            failed_rows = 0
            
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
                        "video_url": row.get("video_url", "")  # 添加视频URL字段
                    }
                    
                    # 处理笔记数据
                    success, message, task_ids = self.note_service.process_note(
                        note_data, 
                        ocr_engine=ocr_engine,
                        process_video=process_video,  # 添加视频处理参数
                        video_engine=video_engine     # 添加视频引擎参数
                    )
                    
                    if success:
                        processed_rows += 1
                        logger.info(f"成功处理行 {index+1}: {message}")
                    else:
                        failed_rows += 1
                        logger.warning(f"处理行 {index+1} 失败: {message}")
                    
                except Exception as e:
                    failed_rows += 1
                    logger.error(f"处理行 {index+1} 时出错: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # 更新每一行的处理结果
            updated_rows = 0
            for index, row in df.iterrows():
                try:
                    note_url = row["note_url"]
                    if not note_url:
                        continue
                    
                    # 获取OCR结果
                    ocr_result = self.note_service.get_note_ocr_results(note_url)
                    if ocr_result:
                        df.at[index, "image_txt"] = ocr_result
                        updated_rows += 1
                        logger.info(f"已更新行 {index+1} 的OCR结果，长度: {len(ocr_result)}")
                    
                    # 获取视频处理结果
                    if process_video:
                        video_result = self.note_service.get_note_video_results(note_url)
                        if video_result:
                            df.at[index, "video_txt"] = video_result
                            logger.info(f"已更新行 {index+1} 的视频处理结果，长度: {len(video_result)}")
                except Exception as e:
                    logger.error(f"更新行 {index+1} 的处理结果时出错: {str(e)}")
                    logger.error(traceback.format_exc())
            
            logger.info(f"共更新了 {updated_rows}/{total_rows} 行的处理结果")
            
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
    
    def update_csv_with_results(self, file_path: str, include_video: bool = False) -> Tuple[bool, str, Optional[str]]:
        """
        使用处理结果更新CSV文件
        
        参数:
            file_path (str): CSV文件路径
            include_video (bool): 是否包含视频处理结果
            
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
            if include_video:
                df = add_column_if_not_exists(df, "video_txt", "")
            
            # 处理每一行数据
            total_rows = len(df)
            updated_rows = 0
            
            for index, row in df.iterrows():
                try:
                    # 获取笔记URL
                    note_url = row.get("note_url")
                    if not note_url:
                        logger.warning(f"行 {index+1} 缺少笔记URL，跳过")
                        continue
                    
                    # 获取处理结果
                    if include_video:
                        # 获取所有结果（包括图片和视频）
                        success, message, result_text = self.note_service.get_note_all_results(note_url)
                    else:
                        # 只获取图片OCR结果
                        result_text = self.note_service.get_note_ocr_results(note_url)
                        success = bool(result_text)
                    
                    if success and result_text:
                        # 更新结果列
                        if include_video:
                            # 分别获取图片和视频结果
                            ocr_text = self.note_service.get_note_ocr_results(note_url)
                            video_text = self.note_service.get_note_video_results(note_url)
                            
                            # 更新对应的列
                            if ocr_text:
                                df.at[index, "image_txt"] = ocr_text
                            if video_text:
                                df.at[index, "video_txt"] = video_text
                        else:
                            # 只更新图片OCR结果
                            df.at[index, "image_txt"] = result_text
                        
                        updated_rows += 1
                        logger.info(f"成功更新行 {index+1} 的处理结果")
                    else:
                        logger.warning(f"行 {index+1} 没有处理结果")
                
                except Exception as e:
                    logger.error(f"更新行 {index+1} 时出错: {str(e)}")
                    logger.error(traceback.format_exc())
            
            logger.info(f"共更新了 {updated_rows}/{total_rows} 行的处理结果")
            
            # 生成输出文件路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(
                config.RESULT_DIR, 
                f"updated_{os.path.basename(file_path).split('.')[0]}_{timestamp}.csv"
            )
            
            # 写入CSV文件
            success = write_csv(df, output_file)
            if not success:
                return False, "写入输出CSV文件失败", None
            
            return True, f"成功更新 {updated_rows}/{total_rows} 行的OCR结果", output_file
            
        except Exception as e:
            logger.error(f"更新CSV文件时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"更新CSV文件时出错: {str(e)}", None
    
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