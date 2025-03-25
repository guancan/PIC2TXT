"""
PaddleOCR服务模块
负责调用PaddleOCR引擎进行图片文字识别
"""

import os
import logging
import time
import importlib.util
from services.ocr.base_ocr import BaseOCRService

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PaddleOCRService(BaseOCRService):
    def __init__(self, result_dir):
        """初始化PaddleOCR服务"""
        super().__init__(result_dir)
        
        # 检查PaddleOCR是否已安装
        self.paddle_installed = self._check_paddle_installation()
        self.ocr = None
        
        # 如果PaddleOCR已安装，初始化OCR引擎
        if self.paddle_installed:
            try:
                from paddleocr import PaddleOCR
                # 初始化PaddleOCR，设置为中英文识别，使用方向分类器
                self.ocr = PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=False)
                logger.info("PaddleOCR引擎初始化成功")
            except Exception as e:
                logger.error(f"初始化PaddleOCR引擎时出错: {str(e)}")
                self.ocr = None
    
    def _check_paddle_installation(self):
        """检查PaddleOCR是否已安装"""
        paddle_spec = importlib.util.find_spec("paddle")
        paddleocr_spec = importlib.util.find_spec("paddleocr")
        
        if paddle_spec is None or paddleocr_spec is None:
            logger.warning("未检测到PaddlePaddle或PaddleOCR，请先安装")
            return False
        
        return True
    
    def check_installation(self):
        """检查OCR引擎是否正确安装"""
        if not self.paddle_installed:
            logger.error("未安装PaddlePaddle或PaddleOCR")
            return False
        
        if self.ocr is None:
            logger.error("PaddleOCR引擎初始化失败")
            return False
        
        return True
    
    def process_image(self, image_path, timeout=60):
        """
        处理图片，执行OCR识别
        
        参数:
            image_path (str): 图片文件路径
            timeout (int): 超时时间（秒）
            
        返回:
            dict: 包含OCR结果的字典
        """
        if not self.check_installation():
            return {
                "success": False,
                "error": "OCR引擎未正确安装或初始化"
            }
        
        if not os.path.exists(image_path):
            return {
                "success": False,
                "error": f"文件不存在: {image_path}"
            }
        
        try:
            # 记录开始时间
            start_time = time.time()
            logger.info(f"开始处理图片: {image_path}")
            
            # 执行OCR识别
            result = self.ocr.ocr(image_path, cls=True)
            
            # 提取文本内容
            text_content = ""
            if result and len(result) > 0:
                for line in result:
                    for item in line:
                        text_content += item[1][0] + "\n"
            
            # 生成输出文件路径
            file_name = os.path.basename(image_path)
            file_base = os.path.splitext(file_name)[0]
            output_txt = os.path.join(self.result_dir, f"{file_base}_paddle.txt")
            
            # 保存OCR结果到文件
            with open(output_txt, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            # 记录处理时间
            elapsed_time = time.time() - start_time
            logger.info(f"图片处理完成: {image_path}, 耗时: {elapsed_time:.2f}秒")
            
            logger.debug(f"OCR结果: {result}")
            logger.debug(f"提取的文本内容长度: {len(text_content)}")
            logger.debug(f"输出文件路径: {output_txt}")
            
            return {
                "success": True,
                "text_content": text_content,
                "result_path": output_txt
            }
        except Exception as e:
            logger.error(f"OCR处理时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"OCR处理时出错: {str(e)}"
            } 