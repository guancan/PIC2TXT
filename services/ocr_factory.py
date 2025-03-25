"""
OCR服务工厂模块
负责创建不同的OCR服务实例
"""

import logging
import config
from services.ocr.paddle_ocr import PaddleOCRService
from services.ocr.mistral_ocr import MistralOCRService
from services.ocr.mistral_nlp import MistralNLPService
from database.models import OCR_ENGINE_LOCAL, OCR_ENGINE_MISTRAL, OCR_ENGINE_NLP

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OCRFactory:
    @staticmethod
    def create_ocr_service(service_type=None, **kwargs):
        """
        创建OCR服务实例
        
        参数:
            service_type (str): 服务类型，可选值: "local"(本地PaddleOCR)、"mistral"(Mistral AI OCR)或"nlp"(自然语言分析)
            **kwargs: 传递给OCR服务的其他参数
            
        返回:
            BaseOCRService: OCR服务实例
        """
        # 如果未指定服务类型，使用默认配置
        if service_type is None:
            service_type = config.DEFAULT_OCR_ENGINE
        
        # 获取结果目录
        result_dir = kwargs.get('result_dir', config.RESULT_DIR)
        
        if service_type.lower() == OCR_ENGINE_LOCAL:
            logger.info("创建本地PaddleOCR服务")
            return PaddleOCRService(result_dir=result_dir)
        elif service_type.lower() == OCR_ENGINE_MISTRAL:
            logger.info("创建Mistral AI OCR服务")
            api_key = kwargs.get('api_key', config.MISTRAL_API_KEY)
            return MistralOCRService(result_dir=result_dir, api_key=api_key)
        elif service_type.lower() == OCR_ENGINE_NLP:
            logger.info("创建Mistral AI 自然语言分析服务")
            api_key = kwargs.get('api_key', config.MISTRAL_API_KEY)
            return MistralNLPService(result_dir=result_dir, api_key=api_key)
        else:
            logger.warning(f"未知的服务类型: {service_type}，使用默认的本地PaddleOCR服务")
            return PaddleOCRService(result_dir=result_dir) 