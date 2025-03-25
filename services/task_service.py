"""
任务处理服务模块
负责管理和执行下载和OCR任务
"""

import os
import logging
import time
from datetime import datetime
from database.models import TASK_STATUS_PENDING, TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED
from database.db_manager import DatabaseManager  # 修改为使用DatabaseManager
from services.download_service import DownloadService  # 更新导入名称
from services.ocr_factory import OCRFactory
import config

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaskService:
    def __init__(self, download_dir=None, result_dir=None):
        """初始化任务服务"""
        self.download_dir = download_dir or config.DOWNLOAD_DIR
        self.result_dir = result_dir or config.RESULT_DIR
        self.db_manager = DatabaseManager(config.DB_PATH)  # 使用DatabaseManager
        self.downloader = DownloadService(self.download_dir)
        
        # 确保目录存在
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.result_dir, exist_ok=True)
    
    def create_task(self, url, ocr_engine="local"):
        """
        创建新任务
        
        参数:
            url (str): 图片或PDF的URL
            ocr_engine (str): OCR引擎类型，可选值: "local"(本地PaddleOCR) 或 "mistral"(Mistral AI)
            
        返回:
            int: 任务ID
        """
        # 创建任务记录
        task_id = self.db_manager.create_task(url=url, ocr_engine=ocr_engine)  # 确保传递ocr_engine参数
        logger.info(f"创建任务 ID: {task_id}, URL: {url}, OCR引擎: {ocr_engine}")
        return task_id
    
    def process_task(self, task_id):
        """
        处理任务
        
        参数:
            task_id (int): 任务ID
            
        返回:
            bool: 处理是否成功
        """
        # 获取任务信息
        task = self.db_manager.get_task(task_id)  # 使用db_manager获取任务
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return False
        
        url = task["url"]
        ocr_engine = task.get("ocr_engine", "local")
        
        # 更新任务状态为处理中
        self.db_manager.update_task_status(task_id, TASK_STATUS_PROCESSING)  # 使用db_manager更新状态
        
        try:
            # 下载文件
            logger.info(f"开始下载: {url}")
            file_path = self.downloader.download_file(url)
            
            if not file_path:
                error_msg = "下载失败"
                logger.error(f"下载失败: {error_msg}")
                self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, error_msg)  # 使用db_manager更新状态
                return False
            
            self.db_manager.update_task_file_path(task_id, file_path)  # 使用db_manager更新文件路径
            
            # 创建OCR服务实例
            ocr_service = OCRFactory.create_ocr_service(service_type=ocr_engine, result_dir=self.result_dir)
            
            # 执行OCR识别
            logger.info(f"开始OCR识别: {file_path}")
            ocr_result = ocr_service.process_image(file_path)
            
            if not ocr_result["success"]:
                error_msg = ocr_result["error"]
                logger.error(f"OCR识别失败: {error_msg}")
                self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, error_msg)  # 使用db_manager更新状态
                return False
            
            # 保存OCR结果
            text_content = ocr_result["text_content"]
            result_path = ocr_result["result_path"]
            
            self.db_manager.create_result(task_id, text_content, result_path)  # 使用db_manager创建结果
            
            logger.info(f"任务完成: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"处理任务时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, str(e))  # 使用db_manager更新状态
            return False
    
    def get_task(self, task_id):
        """获取任务信息"""
        return self.db_manager.get_task(task_id)  # 使用db_manager获取任务
    
    def get_all_tasks(self):
        """获取所有任务"""
        return self.db_manager.get_all_tasks()  # 使用db_manager获取所有任务
    
    def get_task_result(self, task_id):
        """获取任务结果"""
        results = self.db_manager.get_results_by_task(task_id)  # 使用db_manager获取结果
        return results[0] if results else None  # 返回第一个结果 