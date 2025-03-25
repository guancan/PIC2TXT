"""
Mistral AI OCR服务模块
负责调用Mistral AI API进行图片文字识别
"""

import os
import logging
import time
import json
import requests
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MistralOCRService:
    def __init__(self, api_key=None, result_dir="data/results"):
        """初始化Mistral AI OCR服务"""
        self.result_dir = result_dir
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        
        if not self.api_key:
            logger.warning("未设置Mistral API密钥，请设置环境变量MISTRAL_API_KEY或在初始化时提供")
        
        # 确保结果目录存在且有写入权限
        try:
            os.makedirs(self.result_dir, exist_ok=True)
            # 测试写入权限
            test_file = os.path.join(self.result_dir, "test_write.txt")
            with open(test_file, 'w') as f:
                f.write("Test")
            os.remove(test_file)
            logger.info(f"结果目录 {self.result_dir} 已创建并具有写入权限")
        except Exception as e:
            logger.error(f"创建结果目录或测试写入权限时出错: {str(e)}")
    
    def process_image(self, image_path, timeout=60):
        """
        处理图片，执行OCR识别
        
        参数:
            image_path (str): 图片文件路径
            timeout (int): 超时时间（秒）
            
        返回:
            dict: 包含OCR结果的字典
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "未设置Mistral API密钥"
            }
        
        start_time = time.time()
        logger.info(f"开始处理图片: {image_path}")
        
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "error": f"文件不存在: {image_path}"
                }
            
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
                url_response = requests.get(
                    f"https://api.mistral.ai/v1/files/{file_id}/url",
                    headers=headers
                )
                
                if url_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"获取文件URL失败: {url_response.text}"
                    }
                
                signed_url = url_response.json().get('url')
                
                # 处理OCR
                payload = {
                    "model": "mistral-ocr-latest",
                    "document": {
                        "type": "document_url",
                        "document_url": signed_url
                    }
                }
            else:
                # 处理图片文件
                import base64
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