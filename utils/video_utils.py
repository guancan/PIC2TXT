"""
视频处理工具函数
提供视频URL验证、结果格式化和字幕提取功能
"""

import re
import logging
import json
from urllib.parse import urlparse

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_valid_video_url(url):
    """
    验证视频URL是否有效
    
    参数:
        url (str): 要验证的URL
        
    返回:
        bool: URL是否有效
    """
    if not url or not isinstance(url, str):
        return False
    
    # 去除URL前后的空白字符
    url = url.strip()
    
    # 基本URL格式验证
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False
        
        # 检查协议是否为http或https
        if result.scheme not in ['http', 'https']:
            return False
    except Exception as e:
        logger.error(f"URL解析错误: {str(e)}")
        return False
    
    # 小红书视频URL特殊处理 - 它们通常使用GUID格式且不带文件扩展名
    if 'xiaohongshu.com' in result.netloc or 'xhscdn.com' in result.netloc:
        logger.info(f"检测到小红书URL: {url}")
        # 小红书URL可能是以下格式之一:
        # 1. https://www.xiaohongshu.com/{guid}
        # 2. https://www.xiaohongshu.com/discovery/item/{guid}
        # 3. https://www.xiaohongshu.com/explore/{guid}
        # 4. https://www.xiaohongshu.com/explore/xxxx/{guid}
        
        # 检查是否包含有效的GUID格式
        guid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        if re.search(guid_pattern, url):
            logger.info(f"小红书URL包含有效的GUID: {url}")
            return True
        
        # 检查其他可能的小红书视频URL格式
        path_parts = [p for p in result.path.split('/') if p]
        if len(path_parts) >= 1:
            # 如果路径部分至少有一个元素，可能是视频ID
            logger.info(f"可能的小红书视频ID: {path_parts[-1]}")
            return True
            
        logger.warning(f"无法识别的小红书URL格式: {url}")
        return False
    
    # 其他主要视频平台的特殊处理
    video_platforms = [
        'youtube.com', 'youtu.be',  # YouTube
        'vimeo.com',                # Vimeo
        'bilibili.com', 'b23.tv',   # B站
        'douyin.com',               # 抖音
        'kuaishou.com',             # 快手
        'ixigua.com',               # 西瓜视频
        'weibo.com',                # 微博
        'qq.com/video',             # 腾讯视频
        'iqiyi.com'                 # 爱奇艺
    ]
    
    if any(platform in result.netloc for platform in video_platforms):
        logger.info(f"检测到视频平台URL: {url}")
        return True
    
    # 检查常见视频和音频文件扩展名
    video_extensions = [
        '.mp4', '.avi', '.mov', '.flv', '.mkv', '.wmv',  # 视频格式
        '.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus'  # 音频格式
    ]
    
    # 如果URL路径以视频扩展名结尾，或者包含这些扩展名（考虑到URL可能有查询参数）
    path = result.path.lower()
    if any(path.endswith(ext) for ext in video_extensions) or any(ext in path for ext in video_extensions):
        logger.info(f"检测到带扩展名的视频URL: {url}")
        return True
    
    # 检查是否包含视频流相关参数
    query_params = result.query.lower()
    video_params = ['video', 'stream', 'media', 'play', 'watch', 'v=', 'mp4', 'hls', 'dash']
    if any(param in query_params for param in video_params):
        logger.info(f"检测到可能的视频流URL: {url}")
        return True
    
    logger.warning(f"URL不符合已知视频格式: {url}")
    return False

def format_subtitle_text(json_result):
    """
    从JSON结果中提取并格式化字幕文本
    
    参数:
        json_result (dict): 阿里云Paraformer API返回的JSON结果
        
    返回:
        str: 格式化后的字幕文本
    """
    if not json_result:
        return ""
    
    formatted_text = ""
    
    # 处理单个结果
    if isinstance(json_result, dict):
        if 'transcripts' in json_result:
            for transcript in json_result['transcripts']:
                if 'text' in transcript:
                    formatted_text += transcript['text'] + "\n\n"
    
    # 处理结果列表
    elif isinstance(json_result, list):
        for result in json_result:
            if isinstance(result, dict) and 'transcripts' in result:
                for transcript in result['transcripts']:
                    if 'text' in transcript:
                        formatted_text += transcript['text'] + "\n\n"
    
    return formatted_text.strip()

def extract_subtitles_from_response(response_output):
    """
    从阿里云Paraformer API响应中提取字幕
    
    参数:
        response_output (dict): API响应的output部分
        
    返回:
        tuple: (all_text, all_results) 字幕文本和完整结果
    """
    all_text = ""
    all_results = []
    
    if 'results' not in response_output:
        logger.warning("响应中没有results字段")
        return all_text, all_results
    
    for transcription in response_output['results']:
        if transcription.get('subtask_status') == 'SUCCEEDED':
            if 'transcription_result' in transcription:
                # 直接使用结果
                result = transcription['transcription_result']
                all_results.append(result)
                
                # 提取文本
                if 'transcripts' in result:
                    for transcript in result['transcripts']:
                        if 'text' in transcript:
                            all_text += transcript['text'] + "\n\n"
            elif 'transcription_url' in transcription:
                # 需要从URL获取结果，但这部分已在VideoService中处理
                pass
        else:
            logger.warning(f"转写子任务失败: {transcription.get('subtask_status')}")
            if 'message' in transcription:
                logger.warning(f"错误信息: {transcription['message']}")
    
    return all_text.strip(), all_results 