"""
任务处理服务模块
负责管理和执行下载和OCR任务
"""

import os
import logging
import time
import traceback
import random
from datetime import datetime
from database.models import TASK_STATUS_PENDING, TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_TYPE_IMAGE, TASK_TYPE_VIDEO, VIDEO_ENGINE_ALI_PARAFORMER
from database.db_manager import DatabaseManager  # 修改为使用DatabaseManager
from services.download_service import DownloadService  # 更新导入名称
from services.ocr_factory import OCRFactory
from services.video_service import VideoService
import config
import uuid
import concurrent.futures

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
        self.video_service = VideoService(self.result_dir)  # 添加视频服务
        
        # 添加任务处理的频率控制
        self.last_task_time = 0
        self.min_task_interval = 1.0  # 最小任务处理间隔（秒）
        self.max_retries = 2  # 任务处理最大重试次数
        
        # 确保目录存在
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.result_dir, exist_ok=True)
    
    def _wait_for_rate_limit(self):
        """等待以控制任务处理频率"""
        current_time = time.time()
        elapsed = current_time - self.last_task_time
        
        if elapsed < self.min_task_interval:
            wait_time = self.min_task_interval - elapsed + random.uniform(0.1, 0.3)  # 添加随机抖动
            logger.info(f"等待 {wait_time:.2f} 秒以控制任务处理频率")
            time.sleep(wait_time)
        
        self.last_task_time = time.time()
    
    def create_task(self, url=None, file_path=None, ocr_engine="local"):
        """
        创建新任务
        
        参数:
            url (str, optional): 图片或PDF的URL
            file_path (str, optional): 本地文件路径
            ocr_engine (str): OCR引擎类型，可选值: "local"(本地PaddleOCR) 或 "mistral"(Mistral AI)
            
        返回:
            int: 任务ID
        """
        # 创建任务记录
        task_id = self.db_manager.create_task(url=url, file_path=file_path, ocr_engine=ocr_engine)
        logger.info(f"创建任务 ID: {task_id}, URL: {url}, 文件路径: {file_path}, OCR引擎: {ocr_engine}")
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
        
        url = task.get("url")
        file_path = task.get("file_path")
        ocr_engine = task.get("ocr_engine", "local")
        
        # 更新任务状态为处理中
        self.db_manager.update_task_status(task_id, TASK_STATUS_PROCESSING)  # 使用db_manager更新状态
        
        # 控制任务处理频率
        self._wait_for_rate_limit()
        
        # 添加重试逻辑
        retry_count = 0
        retry_delay = 2  # 初始重试延迟（秒）
        
        while retry_count <= self.max_retries:
            try:
                # 如果有URL但没有文件路径，则下载文件
                if url and not file_path:
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
                    
                    # 如果是API频率限制或网络错误，尝试重试
                    if "频率限制" in error_msg or "Max retries exceeded" in error_msg or "SSLError" in error_msg:
                        retry_count += 1
                        if retry_count > self.max_retries:
                            logger.error(f"达到最大重试次数 ({self.max_retries})，任务失败")
                            self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, error_msg)
                            return False
                        
                        wait_time = retry_delay * (1 + random.random())
                        logger.warning(f"任务处理失败，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                        time.sleep(wait_time)
                        retry_delay *= 2  # 指数退避
                        continue
                    else:
                        # 其他错误直接失败
                        self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, error_msg)
                        return False
                
                # 保存OCR结果
                text_content = ocr_result["text_content"]
                result_path = ocr_result["result_path"]
                
                self.db_manager.create_result(task_id, text_content, result_path)  # 使用db_manager创建结果
                
                # 更新任务状态为已完成
                self.db_manager.update_task_status(task_id, TASK_STATUS_COMPLETED)
                
                logger.info(f"任务完成: {task_id}")
                return True
                
            except Exception as e:
                logger.error(f"处理任务时出错: {str(e)}")
                logger.error(traceback.format_exc())
                
                # 尝试重试
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"达到最大重试次数 ({self.max_retries})，任务失败")
                    self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, str(e))
                    return False
                
                wait_time = retry_delay * (1 + random.random())
                logger.warning(f"任务处理出错，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                time.sleep(wait_time)
                retry_delay *= 2  # 指数退避
        
        # 如果执行到这里，说明所有重试都失败了
        self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, "达到最大重试次数后仍然失败")
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
    
    def delete_task(self, task_id):
        """
        删除单个任务
        
        参数:
            task_id (int): 任务ID
            
        返回:
            bool: 删除是否成功
        """
        try:
            logger.info(f"尝试删除任务: {task_id}")
            result = self.db_manager.delete_task(task_id)
            logger.info(f"删除任务结果: {result}, 任务ID: {task_id}")
            return result
        except Exception as e:
            logger.error(f"删除任务 {task_id} 失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def delete_all_tasks(self):
        """
        删除所有任务
        
        返回:
            int: 删除的任务数量
        """
        tasks = self.db_manager.get_all_tasks()
        count = 0
        
        for task in tasks:
            try:
                logger.info(f"尝试删除任务: {task['id']}")
                result = self.db_manager.delete_task(task['id'])
                if result:
                    count += 1
                    logger.info(f"成功删除任务: {task['id']}")
                else:
                    logger.warning(f"删除任务失败: {task['id']}")
            except Exception as e:
                logger.error(f"删除任务 {task['id']} 出现异常: {str(e)}")
                logger.error(traceback.format_exc())
        
        logger.info(f"已删除 {count}/{len(tasks)} 个任务")
        return count

    def create_video_task(self, url=None, file_path=None, video_engine=VIDEO_ENGINE_ALI_PARAFORMER, params=None):
        """
        创建视频处理任务
        
        参数:
            url (str, optional): 视频URL
            file_path (str, optional): 本地视频文件路径
            video_engine (str): 视频处理引擎类型
            params (dict): 视频处理参数
            
        返回:
            int: 任务ID
        """
        # 创建任务记录
        task_id = self.db_manager.create_task(
            url=url, 
            file_path=file_path, 
            task_type=TASK_TYPE_VIDEO,
            video_engine=video_engine
        )
        logger.info(f"创建视频任务 ID: {task_id}, URL: {url}, 文件路径: {file_path}, 视频引擎: {video_engine}")
        
        # 如果需要立即处理，可以在这里调用process_video_task方法
        
        return task_id

    def process_video_task(self, task_id):
        """处理视频任务"""
        retry_count = 0
        retry_delay = 2  # 初始重试延迟（秒）
        
        while retry_count <= self.max_retries:
            try:
                # 获取任务信息
                task = self.db_manager.get_task(task_id)
                if not task:
                    logger.error(f"未找到任务 ID: {task_id}")
                    return False
                
                # 更新任务状态为处理中
                self.db_manager.update_task_status(task_id, TASK_STATUS_PROCESSING)
                
                url = task.get("url")
                file_path = task.get("file_path")
                params = task.get("params", {})
                
                # 如果有URL但没有文件路径，则下载文件
                if url and not file_path:
                    logger.info(f"开始下载视频: {url}")
                    
                    # 检查是否是小红书URL
                    if 'xiaohongshu.com' in url or 'xhscdn.com' in url:
                        logger.info(f"检测到小红书视频URL: {url}")
                        # 小红书视频需要特殊处理，直接传递URL给视频服务
                        video_result = self.video_service.process_video(url, params)
                        
                        # 处理结果
                        if video_result.get("success"):
                            # 保存处理结果
                            text_content = video_result.get("text_content", "")
                            result_path = video_result.get("result_path", "")
                            
                            self.db_manager.create_result(task_id, text_content, result_path)
                            
                            # 更新任务状态为已完成
                            self.db_manager.update_task_status(task_id, TASK_STATUS_COMPLETED)
                            
                            logger.info(f"视频任务完成: {task_id}")
                            return True
                        else:
                            # 处理失败
                            error_msg = video_result.get("error", "未知错误")
                            logger.error(f"视频处理失败: {error_msg}")
                            self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, error_msg)
                            return False
                    else:
                        # 其他视频尝试下载
                        file_path = self.downloader.download_file(url)
                        
                        if not file_path:
                            error_msg = "下载视频失败"
                            logger.error(f"下载失败: {error_msg}")
                            self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, error_msg)
                            return False
                        
                        self.db_manager.update_task_file_path(task_id, file_path)
                
                # 如果有文件路径，则处理视频
                if file_path:
                    logger.info(f"开始处理视频: {file_path}")
                    video_result = self.video_service.process_video(file_path, params)
                    
                    # 处理结果
                    if video_result.get("success"):
                        # 保存处理结果
                        text_content = video_result.get("text_content", "")
                        result_path = video_result.get("result_path", "")
                        
                        self.db_manager.create_result(task_id, text_content, result_path)
                        
                        # 更新任务状态为已完成
                        self.db_manager.update_task_status(task_id, TASK_STATUS_COMPLETED)
                        
                        logger.info(f"视频任务完成: {task_id}")
                        return True
                    else:
                        # 处理失败
                        error_msg = video_result.get("error", "未知错误")
                        logger.error(f"视频处理失败: {error_msg}")
                        self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, error_msg)
                        return False
                
                # 如果既没有URL也没有文件路径，则报错
                if not url and not file_path:
                    error_msg = "任务没有URL或文件路径"
                    logger.error(error_msg)
                    self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, error_msg)
                    return False
                
            except Exception as e:
                logger.error(f"处理视频任务时出错: {str(e)}")
                logger.error(traceback.format_exc())
                
                # 尝试重试
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"达到最大重试次数 ({self.max_retries})，任务失败")
                    self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, str(e))
                    return False
                
                wait_time = retry_delay * (1 + random.random())
                logger.warning(f"任务处理出错，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                time.sleep(wait_time)
                retry_delay *= 2  # 指数退避
        
        # 如果执行到这里，说明所有重试都失败了
        self.db_manager.update_task_status(task_id, TASK_STATUS_FAILED, "达到最大重试次数后仍然失败")
        return False

    def get_task_status(self, task_id):
        """获取任务状态信息"""
        task = self.db_manager.get_task(task_id)
        if not task:
            return None
        
        return {
            "status": task.get("status"),
            "error_message": task.get("error_message")
        }

    def process_tasks_in_parallel(self, task_ids, max_workers=5):
        """
        并行处理多个任务
        
        参数:
            task_ids (List[int]): 任务ID列表
            max_workers (int): 最大并行工作线程数
            
        返回:
            Dict[int, bool]: 任务ID到处理结果的映射
        """
        results = {}
        
        # 将任务分为图片任务和视频任务
        image_tasks = []
        video_tasks = []
        
        for task_id in task_ids:
            task = self.get_task(task_id)
            if not task:
                results[task_id] = False
                continue
                
            if task.get("task_type") == TASK_TYPE_IMAGE:
                image_tasks.append(task_id)
            elif task.get("task_type") == TASK_TYPE_VIDEO:
                video_tasks.append(task_id)
        
        logger.info(f"开始并行处理 {len(image_tasks)} 个图片任务和 {len(video_tasks)} 个视频任务")
        
        # 使用线程池并行处理任务
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有图片任务
            image_futures = {executor.submit(self.process_task, task_id): task_id for task_id in image_tasks}
            
            # 提交所有视频任务
            video_futures = {executor.submit(self.process_video_task, task_id): task_id for task_id in video_tasks}
            
            # 合并所有future
            all_futures = {**image_futures, **video_futures}
            
            # 等待所有任务完成
            for future in concurrent.futures.as_completed(all_futures):
                task_id = all_futures[future]
                try:
                    success = future.result()
                    results[task_id] = success
                except Exception as e:
                    logger.error(f"处理任务 {task_id} 时出错: {str(e)}")
                    results[task_id] = False
        
        return results

    def process_tasks_parallel(self, tasks, max_workers=None):
        """
        并行处理多个任务
        
        参数:
            tasks (list): 任务列表，每个任务是一个字典，包含任务信息
            max_workers (int): 最大工作线程数，默认为None（使用系统默认值）
            
        返回:
            list: 处理结果列表
        """
        if not tasks:
            return []
        
        # 如果未指定max_workers，根据任务数量和CPU核心数确定
        if max_workers is None:
            import multiprocessing
            max_workers = min(len(tasks), multiprocessing.cpu_count() * 2)
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(self.process_task, task): task for task in tasks
            }
            
            # 获取结果
            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"任务完成: {task.get('id', 'unknown')}")
                except Exception as e:
                    logger.error(f"处理任务时出错: {str(e)}")
                    logger.error(traceback.format_exc())
                    results.append({
                        "success": False,
                        "error": f"处理任务时出错: {str(e)}",
                        "task_id": task.get('id', -1)
                    })
        
        return results