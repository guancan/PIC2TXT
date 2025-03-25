"""
文件处理工具
提供文件操作和路径管理功能
"""

import os
import shutil
from pathlib import Path
import logging
import uuid

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_dir(directory):
    """
    确保目录存在，如果不存在则创建
    
    参数:
        directory (str): 目录路径
    """
    os.makedirs(directory, exist_ok=True)

def get_file_extension(file_path):
    """
    获取文件扩展名
    
    参数:
        file_path (str): 文件路径
        
    返回:
        str: 文件扩展名（小写）
    """
    return os.path.splitext(file_path)[1].lower()

def is_image_file(file_path):
    """
    检查文件是否为图片
    
    参数:
        file_path (str): 文件路径
        
    返回:
        bool: 是否为图片文件
    """
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    return get_file_extension(file_path) in image_extensions

def is_pdf_file(file_path):
    """
    检查文件是否为PDF
    
    参数:
        file_path (str): 文件路径
        
    返回:
        bool: 是否为PDF文件
    """
    return get_file_extension(file_path) == '.pdf'

def save_uploaded_file(uploaded_file, save_dir="data/uploads"):
    """
    保存上传的文件
    
    参数:
        uploaded_file: Streamlit上传的文件对象
        save_dir (str): 保存目录
        
    返回:
        str: 保存后的文件路径
    """
    ensure_dir(save_dir)
    
    # 生成唯一文件名
    file_extension = get_file_extension(uploaded_file.name)
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(save_dir, unique_filename)
    
    # 保存文件
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    logger.info(f"文件已保存: {file_path}")
    return file_path

def get_all_files(directory, extensions=None):
    """
    获取目录中的所有文件
    
    参数:
        directory (str): 目录路径
        extensions (list): 文件扩展名列表，如果为None则获取所有文件
        
    返回:
        list: 文件路径列表
    """
    files = []
    
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            
            if extensions is None:
                files.append(file_path)
            else:
                if get_file_extension(file_path) in extensions:
                    files.append(file_path)
    
    return files
