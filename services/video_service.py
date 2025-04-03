"""
视频处理服务模块
负责视频字幕提取和结果处理
"""

import os
import json
import time
import logging
import traceback
import random
from urllib import request
from http import HTTPStatus
from pathlib import Path

import dashscope
from dashscope.audio.asr import Transcription

import config

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self, result_dir=None):
        """初始化视频处理服务"""
        self.result_dir = result_dir or config.RESULT_DIR
        self.api_key = config.ALI_PARAFORMER_API_KEY
        
        # 设置API密钥
        dashscope.api_key = self.api_key
        
        # 调整dashscope库的日志级别，只显示WARNING及以上级别
        logging.getLogger('dashscope').setLevel(logging.WARNING)
        
        # 任务重试配置
        self.max_retries = 3
        self.retry_delay = 2  # 初始重试延迟（秒）
        
        # 确保结果目录存在
        os.makedirs(self.result_dir, exist_ok=True)
    
    def process_video(self, file_path, params=None):
        """
        处理视频文件，提取字幕
        
        参数:
            file_path (str): 视频文件路径或URL
            params (dict): 处理参数，包括:
                - language_hints: 语言提示列表，如 ['zh', 'en']
                - diarization_enabled: 是否启用说话人分离
                - speaker_count: 说话人数量（可选）
                
        返回:
            dict: 处理结果，包含:
                - success (bool): 是否成功
                - text_content (str): 提取的文本内容
                - result_path (str): 结果文件路径
                - error (str): 错误信息（如果失败）
                - task_id (str): 阿里云任务ID
        """
        if not self.api_key:
            logger.error("未设置阿里云Paraformer API密钥")
            return {
                "success": False,
                "error": "未设置阿里云Paraformer API密钥"
            }
        
        # 默认参数
        default_params = {
            "language_hints": ["zh", "en"],
            "diarization_enabled": False
        }
        
        # 合并参数
        if params:
            default_params.update(params)
        
        params = default_params
        logger.info(f"处理视频: {file_path}, 参数: {params}")
        
        # 重试逻辑
        retry_count = 0
        retry_delay = self.retry_delay
        
        while retry_count <= self.max_retries:
            try:
                # 准备API调用参数
                api_params = {
                    'model': 'paraformer-v2',
                    'language_hints': params['language_hints'],
                    'diarization_enabled': params['diarization_enabled']
                }
                
                # 如果启用了说话人分离且指定了说话人数量，添加speaker_count参数
                if params['diarization_enabled'] and 'speaker_count' in params:
                    api_params['speaker_count'] = params['speaker_count']
                
                # 判断是URL还是本地文件
                if file_path.startswith(('http://', 'https://')):
                    logger.info(f"处理视频URL: {file_path}")
                    api_params['file_urls'] = [file_path]
                else:
                    logger.info(f"处理本地视频文件: {file_path}")
                    api_params['file'] = file_path
                
                # 提交异步转写任务
                logger.info("正在提交语音识别任务...")
                task_response = Transcription.async_call(**api_params)
                
                if task_response.status_code != HTTPStatus.OK:
                    error_msg = f"提交任务失败: {task_response.status_code}, {task_response.message if hasattr(task_response, 'message') else '未知错误'}"
                    logger.error(error_msg)
                    
                    # 判断是否需要重试
                    if "频率限制" in error_msg or "请求过于频繁" in error_msg:
                        retry_count += 1
                        if retry_count > self.max_retries:
                            return {"success": False, "error": error_msg}
                        
                        wait_time = retry_delay * (1 + random.random())
                        logger.warning(f"API频率限制，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                        time.sleep(wait_time)
                        retry_delay *= 2  # 指数退避
                        continue
                    else:
                        return {"success": False, "error": error_msg}
                
                # 获取任务ID
                ali_task_id = task_response.output.task_id
                logger.info(f"任务已提交，阿里云任务ID: {ali_task_id}")
                
                # 等待转写任务完成
                logger.info("等待转写结果...")
                transcription_response = Transcription.wait(task=ali_task_id)
                
                # 处理转写结果
                if transcription_response.status_code == HTTPStatus.OK:
                    logger.info("转写任务完成，处理结果...")
                    
                    # 用于保存纯文本内容
                    all_text = ""
                    
                    # 用于保存完整的JSON结果
                    all_results = []
                    
                    # 处理结果
                    for transcription in transcription_response.output['results']:
                        if transcription['subtask_status'] == 'SUCCEEDED':
                            url = transcription['transcription_url']
                            logger.info(f"获取转写结果: {url}")
                            
                            # 下载结果
                            result = json.loads(request.urlopen(url).read().decode('utf8'))
                            all_results.append(result)
                            
                            # 提取纯文本内容
                            if 'transcripts' in result:
                                for transcript in result['transcripts']:
                                    if 'text' in transcript:
                                        all_text += transcript['text'] + "\n\n"
                        else:
                            error_msg = f"转写子任务失败：{transcription['subtask_status']}"
                            if 'message' in transcription:
                                error_msg += f", 错误信息：{transcription['message']}"
                            logger.error(error_msg)
                    
                    # 生成时间戳，用于文件名
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    
                    # 生成文件名前缀
                    file_name = os.path.basename(file_path)
                    if file_name.startswith(('http://', 'https://')):
                        file_name = f"video_{timestamp}"
                    else:
                        file_name = os.path.splitext(file_name)[0]
                    
                    # 保存完整JSON结果
                    json_file_path = os.path.join(self.result_dir, f"{file_name}_{timestamp}_full.json")
                    with open(json_file_path, 'w', encoding='utf-8') as f:
                        json.dump(all_results, f, ensure_ascii=False, indent=4)
                    logger.info(f"完整结果已保存到: {json_file_path}")
                    
                    # 保存纯文本结果
                    text_file_path = os.path.join(self.result_dir, f"{file_name}_{timestamp}_text.txt")
                    with open(text_file_path, 'w', encoding='utf-8') as f:
                        f.write(all_text)
                    logger.info(f"文本内容已保存到: {text_file_path}")
                    
                    return {
                        "success": True,
                        "text_content": all_text,
                        "result_path": text_file_path,
                        "json_path": json_file_path,
                        "task_id": ali_task_id
                    }
                else:
                    error_msg = f"转写任务失败: {transcription_response.status_code}, {transcription_response.output.message if hasattr(transcription_response.output, 'message') else '未知错误'}"
                    logger.error(error_msg)
                    
                    # 判断是否需要重试
                    if "频率限制" in error_msg or "请求过于频繁" in error_msg:
                        retry_count += 1
                        if retry_count > self.max_retries:
                            return {"success": False, "error": error_msg, "task_id": ali_task_id}
                        
                        wait_time = retry_delay * (1 + random.random())
                        logger.warning(f"API频率限制，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                        time.sleep(wait_time)
                        retry_delay *= 2  # 指数退避
                        continue
                    else:
                        return {"success": False, "error": error_msg, "task_id": ali_task_id}
                
            except Exception as e:
                error_msg = f"处理视频时出错: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                
                # 尝试重试
                retry_count += 1
                if retry_count > self.max_retries:
                    return {"success": False, "error": error_msg}
                
                wait_time = retry_delay * (1 + random.random())
                logger.warning(f"处理出错，等待 {wait_time:.2f} 秒后重试 ({retry_count}/{self.max_retries})")
                time.sleep(wait_time)
                retry_delay *= 2  # 指数退避
        
        # 如果执行到这里，说明所有重试都失败了
        return {"success": False, "error": "达到最大重试次数后仍然失败"}
    
    def check_task_status(self, ali_task_id):
        """
        检查阿里云任务状态
        
        参数:
            ali_task_id (str): 阿里云任务ID
            
        返回:
            dict: 任务状态信息
        """
        try:
            # 查询任务状态
            status_response = Transcription.fetch(task=ali_task_id)
            
            if status_response.status_code == HTTPStatus.OK:
                task_status = status_response.output.task_status
                logger.info(f"任务 {ali_task_id} 状态: {task_status}")
                
                return {
                    "success": True,
                    "status": task_status,
                    "details": status_response.output
                }
            else:
                error_msg = f"获取任务状态失败: {status_response.status_code}, {status_response.message if hasattr(status_response, 'message') else '未知错误'}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
        except Exception as e:
            error_msg = f"检查任务状态时出错: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": error_msg
            }