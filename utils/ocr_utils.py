"""
OCR相关工具函数
提供OCR结果处理功能
"""

import os
import json
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def save_ocr_result(task_id, text_content, result_dir="data/results"):
    """
    保存OCR结果到文件
    
    参数:
        task_id (int): 任务ID
        text_content (str): OCR识别的文本内容
        result_dir (str): 结果保存目录
        
    返回:
        str: 结果文件路径
    """
    os.makedirs(result_dir, exist_ok=True)
    
    # 生成结果文件路径
    result_file = os.path.join(result_dir, f"task_{task_id}.txt")
    
    # 保存文本内容
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(text_content)
    
    logger.info(f"OCR结果已保存: {result_file}")
    return result_file

def merge_ocr_results(result_files, output_file):
    """
    合并多个OCR结果文件
    
    参数:
        result_files (list): 结果文件路径列表
        output_file (str): 输出文件路径
        
    返回:
        str: 输出文件路径
    """
    merged_content = ""
    
    for file_path in result_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                merged_content += f"=== {os.path.basename(file_path)} ===\n"
                merged_content += content
                merged_content += "\n\n"
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {str(e)}")
    
    # 保存合并后的内容
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(merged_content)
    
    logger.info(f"OCR结果已合并: {output_file}")
    return output_file

def format_ocr_text(text):
    """
    格式化OCR文本结果
    
    参数:
        text (str): 原始OCR文本
        
    返回:
        str: 格式化后的文本
    """
    # 简单的格式化，可以根据需要扩展
    lines = text.splitlines()
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if line:
            formatted_lines.append(line)
    
    return "\n".join(formatted_lines)
