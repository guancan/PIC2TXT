"""
OCR服务基类
定义OCR服务的通用接口
"""

import os
import logging
import time
from abc import ABC, abstractmethod

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseOCRService(ABC):
    def __init__(self, result_dir):
        """
        初始化OCR服务
        
        参数:
            result_dir (str): 结果保存目录
        """
        self.result_dir = result_dir
        
        # 确保结果目录存在
        os.makedirs(self.result_dir, exist_ok=True)
        
        # 测试写入权限
        try:
            test_file = os.path.join(self.result_dir, "test_write.txt")
            with open(test_file, 'w') as f:
                f.write("Test")
            os.remove(test_file)
            logger.info(f"结果目录 {self.result_dir} 已创建并具有写入权限")
        except Exception as e:
            logger.error(f"创建结果目录或测试写入权限时出错: {str(e)}")
    
    @abstractmethod
    def check_installation(self):
        """
        检查OCR服务是否可用
        
        返回:
            bool: 服务是否可用
        """
        pass
    
    @abstractmethod
    def process_image(self, image_path, timeout=60):
        """
        处理图片，执行OCR识别
        
        参数:
            image_path (str): 图片文件路径
            timeout (int): 超时时间（秒）
            
        返回:
            dict: 包含OCR结果的字典
        """
        pass
    
    def process_batch(self, image_paths, max_workers=4):
        """
        批量处理图片
        
        参数:
            image_paths (list): 图片文件路径列表
            max_workers (int): 最大并行处理数量
            
        返回:
            list: 每个图片的OCR结果列表
        """
        results = []
        total = len(image_paths)
        
        logger.info(f"开始批量处理 {total} 个图片")
        
        # 简单的串行处理，避免并发问题
        for i, image_path in enumerate(image_paths):
            logger.info(f"处理图片 {i+1}/{total}: {image_path}")
            result = self.process_image(image_path)
            result["image_path"] = image_path
            results.append(result)
        
        success_count = sum(1 for r in results if r["success"])
        logger.info(f"批量处理完成，成功: {success_count}/{total}")
        
        return results 