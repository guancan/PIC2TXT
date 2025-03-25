"""
下载服务模块
负责从URL下载图片和PDF文件
"""

import os
import requests
import time
from pathlib import Path
from urllib.parse import urlparse
import logging
import re
import mimetypes

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DownloadService:
    def __init__(self, download_dir="data/downloads"):
        """初始化下载器"""
        self.download_dir = download_dir
        # 确保下载目录存在
        os.makedirs(self.download_dir, exist_ok=True)
        # 初始化MIME类型
        mimetypes.init()
    
    def download_file(self, url):
        """
        从URL下载文件
        
        参数:
            url (str): 要下载的文件URL
            
        返回:
            str: 下载文件的本地路径，如果下载失败则返回None
        """
        if not url:
            logger.error("下载失败：URL为空")
            return None
        
        try:
            # 发送请求获取文件
            logger.info(f"开始下载: {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()  # 如果请求失败则抛出异常
            
            # 确定文件扩展名
            extension = self._get_file_extension(url, response)
            
            # 生成文件名
            filename = self._generate_filename(url, extension)
            file_path = os.path.join(self.download_dir, filename)
            
            # 保存文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"下载完成: {file_path}")
            return file_path
        
        except Exception as e:
            logger.error(f"下载失败: {url}, 错误: {str(e)}")
            return None
    
    def _get_file_extension(self, url, response):
        """
        获取文件扩展名
        
        参数:
            url (str): 文件URL
            response (Response): 请求响应对象
            
        返回:
            str: 文件扩展名（带点，如 .jpg）
        """
        # 1. 尝试从Content-Type获取
        content_type = response.headers.get('Content-Type', '')
        if content_type:
            ext = mimetypes.guess_extension(content_type.split(';')[0].strip())
            if ext and ext != '.jpe':  # 避免不常见的.jpe扩展名
                return ext
        
        # 2. 尝试从URL中提取
        # 先检查URL中是否包含明确的图片格式标记
        format_match = re.search(r'_(jpg|jpeg|png|gif|bmp|pdf)_', url, re.IGNORECASE)
        if format_match:
            return f".{format_match.group(1).lower()}"
        
        # 再从URL路径中提取
        parsed_url = urlparse(url)
        path = parsed_url.path
        ext = os.path.splitext(path)[1].lower()
        if ext and ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf']:
            return ext
        
        # 3. 默认返回.jpg
        return '.jpg'
    
    def _generate_filename(self, url, extension):
        """
        生成文件名
        
        参数:
            url (str): 文件URL
            extension (str): 文件扩展名
            
        返回:
            str: 生成的文件名
        """
        # 从URL中提取文件名部分
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # 尝试使用URL中的最后一部分作为文件名基础
        basename = os.path.basename(path)
        
        # 如果basename为空或只有扩展名，则使用URL的哈希值
        if not basename or basename == extension:
            basename = f"img_{hash(url) % 10000:04d}"
        
        # 移除原有扩展名
        basename = os.path.splitext(basename)[0]
        
        # 确保文件名合法（移除非法字符）
        basename = re.sub(r'[\\/*?:"<>|]', '_', basename)
        
        # 添加时间戳避免文件名冲突
        timestamp = int(time.time())
        filename = f"{basename}_{timestamp}{extension}"
        
        return filename
    
    def download_files(self, urls):
        """
        批量下载文件
        
        参数:
            urls (list): 要下载的URL列表
            
        返回:
            list: 成功下载的文件路径列表
        """
        file_paths = []
        for url in urls:
            file_path = self.download_file(url)
            if file_path:
                file_paths.append(file_path)
        return file_paths
    
    def is_valid_url(self, url):
        """
        检查URL是否有效
        
        参数:
            url (str): 要检查的URL
            
        返回:
            bool: URL是否有效
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def get_file_extension(self, file_path):
        """
        获取文件扩展名
        
        参数:
            file_path (str): 文件路径
            
        返回:
            str: 文件扩展名（小写）
        """
        return os.path.splitext(file_path)[1].lower()
    
    def is_supported_file(self, file_path):
        """
        检查文件是否为支持的类型（图片或PDF）
        
        参数:
            file_path (str): 文件路径
            
        返回:
            bool: 文件是否为支持的类型
        """
        supported_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf']
        ext = self.get_file_extension(file_path)
        return ext in supported_extensions
