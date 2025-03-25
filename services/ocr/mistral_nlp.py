"""
Mistral AI 自然语言分析服务模块
负责调用Mistral AI API进行图片内容的自然语言分析
"""

import os
import logging
import time
import base64
import random
from services.ocr.base_ocr import BaseOCRService
from mistralai import Mistral
import config

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MistralNLPService(BaseOCRService):
    def __init__(self, result_dir, api_key=None):
        """
        初始化Mistral AI 自然语言分析服务
        
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
        """检查服务是否可用"""
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
    
    def process_image(self, image_path, timeout=60):
        """
        处理图片，执行自然语言分析
        
        参数:
            image_path (str): 图片文件路径
            timeout (int): 超时时间（秒）
            
        返回:
            dict: 包含分析结果的字典
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
            
            # 初始化Mistral客户端
            client = Mistral(api_key=self.api_key)
            
            # 将图片编码为base64
            try:
                with open(image_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                image_url = f"data:image/jpeg;base64,{base64_image}"
            except Exception as e:
                return {
                    "success": False,
                    "error": f"处理图片文件时出错: {str(e)}"
                }
            
            # 使用自然语言询问图片内容
            retry_count = 0
            current_delay = self.retry_delay
            
            while retry_count <= self.max_retries:
                try:
                    self._wait_for_rate_limit()
                    
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "请以Markdown格式反馈图片内容给我，尽量还原图片中的信息内容和文章结构，如果有插图，则请用语言描述插图内容、放在插图所在段落位置。"
                                },
                                {
                                    "type": "image_url",
                                    "image_url": image_url
                                }
                            ]
                        }
                    ]
                    
                    # 获取响应
                    chat_response = client.chat.complete(
                        model="mistral-small-latest",  # 或使用其他适合的模型
                        messages=messages
                    )
                    
                    # 提取响应内容
                    response_content = chat_response.choices[0].message.content
                    
                    # 生成结果文件
                    base_name = os.path.basename(image_path)
                    file_name = os.path.splitext(base_name)[0]
                    output_txt = os.path.join(self.result_dir, f"{file_name}_mistral_nlp.txt")
                    
                    with open(output_txt, 'w', encoding='utf-8') as f:
                        f.write(response_content)
                    
                    logger.info(f"自然语言分析完成，耗时: {time.time() - start_time:.2f}秒")
                    logger.info(f"结果已保存到: {output_txt}")
                    
                    return {
                        "success": True,
                        "text_content": response_content,
                        "result_path": output_txt
                    }
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count > self.max_retries:
                        logger.error(f"达到最大重试次数 ({self.max_retries})，放弃请求")
                        raise
                    
                    wait_time = current_delay * (1 + random.random())
                    logger.warning(f"请求失败: {str(e)}，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                    time.sleep(wait_time)
                    current_delay *= 2  # 指数退避
            
        except Exception as e:
            logger.error(f"自然语言分析处理时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"自然语言分析处理时出错: {str(e)}"
            } 