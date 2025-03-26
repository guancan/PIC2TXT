"""
CSV处理工具函数
提供CSV文件的读取、解析和写入功能
"""

import os
import csv
import logging
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_csv(file_path: str) -> Optional[pd.DataFrame]:
    """
    读取CSV文件并返回DataFrame
    
    参数:
        file_path (str): CSV文件路径
        
    返回:
        Optional[pd.DataFrame]: 读取的DataFrame，失败则返回None
    """
    try:
        logger.info(f"正在读取CSV文件: {file_path}")
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None
        
        # 尝试自动检测编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16']
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                logger.info(f"成功使用 {encoding} 编码读取CSV文件")
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"读取CSV文件时出错 (编码: {encoding}): {str(e)}")
                continue
        
        logger.error("无法使用任何已知编码读取CSV文件")
        return None
    except Exception as e:
        logger.error(f"读取CSV文件时出现异常: {str(e)}")
        return None

def write_csv(df: pd.DataFrame, file_path: str, encoding: str = 'utf-8') -> bool:
    """
    将DataFrame写入CSV文件
    
    参数:
        df (pd.DataFrame): 要写入的DataFrame
        file_path (str): 输出CSV文件路径
        encoding (str): 文件编码，默认为utf-8
        
    返回:
        bool: 写入是否成功
    """
    try:
        logger.info(f"正在写入CSV文件: {file_path}")
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        df.to_csv(file_path, index=False, encoding=encoding)
        logger.info(f"CSV文件写入成功: {file_path}")
        return True
    except Exception as e:
        logger.error(f"写入CSV文件时出错: {str(e)}")
        return False

def extract_image_urls(image_list_str: str) -> List[str]:
    """
    从image_list字段中提取图片URL列表
    
    参数:
        image_list_str (str): 图片URL字符串，多个URL用逗号分隔
        
    返回:
        List[str]: 图片URL列表
    """
    if not image_list_str or not isinstance(image_list_str, str):
        return []
    
    # 分割字符串并清理每个URL
    urls = [url.strip() for url in image_list_str.split(',') if url.strip()]
    return urls

def validate_csv_structure(df: pd.DataFrame, required_fields: List[str]) -> Tuple[bool, str]:
    """
    验证CSV文件结构是否包含必要的字段
    
    参数:
        df (pd.DataFrame): 要验证的DataFrame
        required_fields (List[str]): 必需的字段列表
        
    返回:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    if df is None or df.empty:
        return False, "CSV文件为空"
    
    missing_fields = [field for field in required_fields if field not in df.columns]
    if missing_fields:
        return False, f"CSV文件缺少必要字段: {', '.join(missing_fields)}"
    
    return True, ""

def add_column_if_not_exists(df: pd.DataFrame, column_name: str, default_value: Any = "") -> pd.DataFrame:
    """
    如果列不存在，则添加新列
    
    参数:
        df (pd.DataFrame): 要修改的DataFrame
        column_name (str): 列名
        default_value (Any): 默认值
        
    返回:
        pd.DataFrame: 修改后的DataFrame
    """
    if column_name not in df.columns:
        df[column_name] = default_value
    return df 