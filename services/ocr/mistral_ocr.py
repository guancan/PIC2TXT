"""
Mistral AI OCR服务模块
负责调用Mistral AI API进行图片文字识别
"""

import os
import logging
import time
import json
import requests
import base64
from services.ocr.base_ocr import BaseOCRService
import config

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MistralOCRService(BaseOCRService):
    def __init__(self, result_dir, api_key=None):
        """
        初始化Mistral AI OCR服务
        
        参数:
            result_dir (str): 结果保存目录
            api_key (str, optional): Mistral API密钥，如果为None则从环境变量获取
        """
        super().__init__(result_dir)
        self.api_key = api_key or config.MISTRAL_API_KEY
        
        if not self.api_key:
            logger.warning("未设置Mistral API密钥，请设置环境变量MISTRAL_API_KEY或在初始化时提供")
    
    def check_installation(self):
        """检查OCR服务是否可用"""
        if not self.api_key:
            logger.error("未设置Mistral API密钥")
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
                "error": "未设置Mistral API密钥"
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
            
            # 获取文件扩展名
            file_ext = os.path.splitext(image_path)[1].lower()
            
            # 准备API请求
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 根据文件类型选择不同的处理方式
            if file_ext in ['.pdf']:
                # 处理PDF文件
                with open(image_path, 'rb') as f:
                    files = {'file': (os.path.basename(image_path), f, 'application/pdf')}
                    upload_response = requests.post(
                        "https://api.mistral.ai/v1/files",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files=files,
                        data={"purpose": "ocr"}
                    )
                
                if upload_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"上传PDF失败: {upload_response.text}"
                    }
                
                file_data = upload_response.json()
                file_id = file_data.get('id')
                
                # 获取签名URL
                url_response = requests.post(
                    "https://api.mistral.ai/v1/files/signed_url",
                    headers=headers,
                    json={"file_id": file_id}
                )
                
                if url_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"获取签名URL失败: {url_response.text}"
                    }
                
                signed_url = url_response.json().get('signed_url')
                
                payload = {
                    "model": "mistral-ocr-latest",
                    "document": {
                        "type": "document_url",
                        "document_url": signed_url
                    }
                }
            else:
                # 处理图片文件
                with open(image_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                payload = {
                    "model": "mistral-ocr-latest",
                    "document": {
                        "type": "image_url",
                        "image_url": f"data:image/{file_ext[1:]};base64,{base64_image}"
                    }
                }
            
            # 发送OCR请求
            response = requests.post(
                "https://api.mistral.ai/v1/ocr",
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"OCR请求失败: {response.text}"
                }
            
            # 解析结果
            result = response.json()
            
            # 提取所有页面的文本内容
            all_text = ""
            for page in result.get('pages', []):
                all_text += page.get('markdown', '') + "\n\n"
            
            # 生成结果文件
            base_name = os.path.basename(image_path)
            file_name = os.path.splitext(base_name)[0]
            output_txt = os.path.join(self.result_dir, f"{file_name}_mistral.txt")
            
            with open(output_txt, 'w', encoding='utf-8') as f:
                f.write(all_text)
            
            logger.info(f"OCR处理完成，耗时: {time.time() - start_time:.2f}秒")
            logger.info(f"结果已保存到: {output_txt}")
            
            return {
                "success": True,
                "text_content": all_text,
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

    def process_images_batch(self, image_paths):
        """
        使用Mistral Batch API批量处理图片
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            批处理任务ID
        """
        try:
            # 1. 上传图片文件
            file_ids = []
            for image_path in image_paths:
                with open(image_path, "rb") as f:
                    response = requests.post(
                        "https://api.mistral.ai/v1/files",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files={"file": f},
                        data={"purpose": "ocr"}
                    )
                    response.raise_for_status()
                    file_ids.append(response.json()["id"])
            
            # 2. 创建批处理任务
            response = requests.post(
                "https://api.mistral.ai/v1/batch/jobs",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input_files": file_ids,
                    "endpoint": "/v1/ocr",
                    "model": "mistral-ocr",  # 使用适当的OCR模型
                    "timeout_hours": 24
                }
            )
            response.raise_for_status()
            
            # 返回批处理任务ID
            return response.json()["id"]
            
        except Exception as e:
            self.logger.error(f"批量OCR处理失败: {str(e)}")
            raise OCRException(f"批量OCR请求失败: {str(e)}") 