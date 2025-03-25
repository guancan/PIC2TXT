"""
OCR服务测试脚本
"""

import os
import sys
import logging
from services.ocr_factory import OCRFactory
import config

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ocr(image_path, ocr_engine="local"):
    """测试OCR服务"""
    # 创建OCR服务实例
    ocr_service = OCRFactory.create_ocr_service(service_type=ocr_engine)
    
    # 检查OCR服务是否可用
    if not ocr_service.check_installation():
        logger.error(f"OCR服务 {ocr_engine} 不可用")
        return False
    
    # 处理图片
    result = ocr_service.process_image(image_path)
    
    if result["success"]:
        logger.info(f"OCR识别成功: {result['result_path']}")
        logger.info(f"文本内容: {result['text_content'][:200]}...")  # 只显示前200个字符
        return True
    else:
        logger.error(f"OCR识别失败: {result['error']}")
        return False

if __name__ == "__main__":
    # 从命令行参数获取图片路径
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        
        # 可选的OCR引擎参数
        ocr_engine = sys.argv[2] if len(sys.argv) > 2 else "local"
        
        if not os.path.exists(image_path):
            logger.error(f"文件不存在: {image_path}")
            sys.exit(1)
        
        success = test_ocr(image_path, ocr_engine)
        sys.exit(0 if success else 1)
    else:
        logger.error("请提供图片路径")
        logger.info("用法: python test_ocr.py <图片路径> [ocr引擎]")
        sys.exit(1) 