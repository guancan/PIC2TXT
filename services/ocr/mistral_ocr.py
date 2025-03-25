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
import random
from services.ocr.base_ocr import BaseOCRService
import config

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加OCRException异常类定义
class OCRException(Exception):
    """OCR处理过程中的异常"""
    pass

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
        
        # 添加重试和频率限制相关参数
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 2  # 初始重试延迟（秒）
        self.last_request_time = 0  # 上次请求时间
        self.min_request_interval = 1.0  # 最小请求间隔（秒）
        
        if not self.api_key:
            logger.warning("未设置Mistral API密钥，请设置环境变量MISTRAL_API_KEY或在初始化时提供")
    
    def check_installation(self):
        """检查OCR服务是否可用"""
        if not self.api_key:
            logger.error("未设置Mistral API密钥")
            return False
        return True
    
    def _wait_for_rate_limit(self):
        """等待以遵守API频率限制"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_request_interval:
            wait_time = self.min_request_interval - elapsed + random.uniform(0.1, 0.5)  # 添加随机抖动
            logger.info(f"等待 {wait_time:.2f} 秒以遵守API频率限制")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _make_api_request(self, url, headers, payload, timeout):
        """发送API请求并处理重试逻辑"""
        retry_count = 0
        current_delay = self.retry_delay
        
        while retry_count <= self.max_retries:
            try:
                self._wait_for_rate_limit()  # 遵守频率限制
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                
                if response.status_code == 429:  # 触发频率限制
                    retry_count += 1
                    wait_time = current_delay * (1 + random.random())
                    logger.warning(f"API频率限制触发，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                    time.sleep(wait_time)
                    current_delay *= 2  # 指数退避
                    continue
                
                return response
                
            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"达到最大重试次数 ({self.max_retries})，放弃请求")
                    raise
                
                wait_time = current_delay * (1 + random.random())
                logger.warning(f"请求失败: {str(e)}，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                time.sleep(wait_time)
                current_delay *= 2  # 指数退避
    
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
                try:
                    with open(image_path, 'rb') as f:
                        files = {'file': (os.path.basename(image_path), f, 'application/pdf')}
                        
                        # 使用重试逻辑上传文件
                        retry_count = 0
                        current_delay = self.retry_delay
                        
                        while retry_count <= self.max_retries:
                            try:
                                self._wait_for_rate_limit()
                                
                                upload_response = requests.post(
                                    "https://api.mistral.ai/v1/files",
                                    headers={"Authorization": f"Bearer {self.api_key}"},
                                    files=files,
                                    data={"purpose": "ocr"}
                                )
                                
                                if upload_response.status_code == 429:
                                    retry_count += 1
                                    wait_time = current_delay * (1 + random.random())
                                    logger.warning(f"上传文件时触发API频率限制，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                                    time.sleep(wait_time)
                                    current_delay *= 2
                                    continue
                                
                                break
                                
                            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                                retry_count += 1
                                if retry_count > self.max_retries:
                                    logger.error(f"上传文件时达到最大重试次数 ({self.max_retries})，放弃请求")
                                    raise
                                
                                wait_time = current_delay * (1 + random.random())
                                logger.warning(f"上传文件失败: {str(e)}，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                                time.sleep(wait_time)
                                current_delay *= 2
                
                    if upload_response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"上传PDF失败: {upload_response.text}"
                        }
                    
                    file_data = upload_response.json()
                    file_id = file_data.get('id')
                    
                    # 获取签名URL
                    url_response = self._make_api_request(
                        "https://api.mistral.ai/v1/files/signed_url",
                        headers,
                        {"file_id": file_id},
                        timeout
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
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"处理PDF文件时出错: {str(e)}"
                    }
            else:
                # 处理图片文件
                try:
                    with open(image_path, 'rb') as image_file:
                        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    
                    payload = {
                        "model": "mistral-ocr-latest",
                        "document": {
                            "type": "image_url",
                            "image_url": f"data:image/{file_ext[1:]};base64,{base64_image}"
                        }
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"处理图片文件时出错: {str(e)}"
                    }
            
            # 发送OCR请求
            try:
                response = self._make_api_request(
                    "https://api.mistral.ai/v1/ocr",
                    headers,
                    payload,
                    timeout
                )
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"OCR请求失败: {response.text}"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"OCR API请求失败: {str(e)}"
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