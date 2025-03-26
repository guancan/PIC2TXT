"""
CSV表格处理服务
提供CSV表格的读取、处理和写入功能，支持小红书笔记数据的处理
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
    
    def process_csv_file(self, file_path: str, ocr_engine: str = "mistral") -> Tuple[bool, str, Optional[str]]:
        """
        处理CSV文件，提取图片链接并创建OCR任务
        
        参数:
            file_path (str): CSV文件路径
            ocr_engine (str): OCR引擎类型
            
        返回:
            Tuple[bool, str, Optional[str]]: (是否成功, 消息, 输出文件路径)
        """
        try:
            # 读取CSV文件
            df = read_csv(file_path)
            if df is None:
                return False, "无法读取CSV文件", None
            
            # 验证CSV结构
            required_fields = ["note_url", "image_list"]
            is_valid, error_msg = validate_csv_structure(df, required_fields)
            if not is_valid:
                return False, error_msg, None
            
            # 添加image_txt列（如果不存在）
            df = add_column_if_not_exists(df, "image_txt", "")
            
            # 记录数据源
            source_id = self._register_data_source(file_path, "csv")
            
            # 处理每一行
            total_rows = len(df)
            processed_rows = 0
            failed_rows = 0
            
            for index, row in df.iterrows():
                try:
                    note_url = row["note_url"]
                    image_list_str = row["image_list"]
                    
                    # 构建笔记数据
                    note_data = {
                        "note_url": note_url,
                        "image_list": image_list_str
                    }
                    
                    # 使用XHSNoteService处理笔记数据
                    success, message, task_ids = self.note_service.process_note(note_data, ocr_engine)
                    
                    if success:
                        processed_rows += 1
                        
                        # 执行创建的任务
                        for task_id in task_ids:
                            self.task_service.process_task(task_id)
                    else:
                        logger.warning(f"行 {index+1}: {message}")
                        failed_rows += 1
                        
                except Exception as e:
                    logger.error(f"处理行 {index+1} 时出错: {str(e)}")
                    logger.error(traceback.format_exc())
                    failed_rows += 1
            
            # 更新每一行的OCR结果
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
                except Exception as e:
                    logger.error(f"更新行 {index+1} 的OCR结果时出错: {str(e)}")
                    logger.error(traceback.format_exc())
            
            logger.info(f"共更新了 {updated_rows}/{total_rows} 行的OCR结果")
            
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
    
    def update_csv_with_results(self, file_path: str) -> Tuple[bool, str, Optional[str]]:
        """
        使用OCR结果更新CSV文件
        
        参数:
            file_path (str): CSV文件路径
            
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
            
            # 添加image_txt列（如果不存在）
            df = add_column_if_not_exists(df, "image_txt", "")
            
            # 处理每一行
            total_rows = len(df)
            updated_rows = 0
            
            for index, row in df.iterrows():
                try:
                    note_url = row["note_url"]
                    
                    # 获取笔记的OCR结果
                    success, message, ocr_text = self.note_service.get_note_ocr_results(note_url)
                    
                    if success and ocr_text:
                        df.at[index, "image_txt"] = ocr_text
                        updated_rows += 1
                    else:
                        logger.warning(f"行 {index+1}: {message}")
                
                except Exception as e:
                    logger.error(f"更新行 {index+1} 时出错: {str(e)}")
                    logger.error(traceback.format_exc())
            
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