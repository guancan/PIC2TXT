import os
import json
import time
from urllib import request
from http import HTTPStatus

import dashscope

# 从环境变量或直接设置API密钥
dashscope.api_key = os.getenv("ALI_PARAFORMER_API_KEY", "sk-fa55a5f883034cd28824116d45d2c171")

# 定义要识别的视频URL
video_url = "https://sns-video-qc.xhscdn.com/stream/1/110/259/01e7d6b2c5250c2801037003959eab8be8_259.mp4?sign=43571d559a8a6a9c2e53f90b27466f01&t=67eee0e3"

# 创建保存结果的目录
results_dir = "data/results"
os.makedirs(results_dir, exist_ok=True)

# 提交异步转写任务
try:
    print("正在提交语音识别任务...")
    task_response = dashscope.audio.asr.Transcription.async_call(
        model='paraformer-v2',
        file_urls=[video_url],
        language_hints=['zh', 'en'],  # 支持中文和英文混合识别
        diarization_enabled=True,     # 启用自动说话人分离
        speaker_count=3               # 指定说话人数量参考值（2-100之间的整数）
    )
    
    task_id = task_response.output.task_id
    print(f"任务已提交，任务ID: {task_id}")
    
    # 等待转写任务完成
    print("等待转写结果...")
    transcription_response = dashscope.audio.asr.Transcription.wait(
        task=task_id
    )
    
    # 处理转写结果
    if transcription_response.status_code == HTTPStatus.OK:
        print("转写任务完成，结果如下：")
        
        # 用于保存纯文本内容
        all_text = ""
        
        # 用于保存完整的JSON结果
        all_results = []
        
        for transcription in transcription_response.output['results']:
            if transcription['subtask_status'] == 'SUCCEEDED':
                url = transcription['transcription_url']
                print(f"获取转写结果: {url}")
                result = json.loads(request.urlopen(url).read().decode('utf8'))
                print(json.dumps(result, indent=4, ensure_ascii=False))
                
                # 将结果添加到列表
                all_results.append(result)
                
                # 提取纯文本内容 - 修复的部分
                if 'transcripts' in result:
                    for transcript in result['transcripts']:
                        if 'text' in transcript:
                            all_text += transcript['text'] + "\n\n"
            else:
                print(f"转写子任务失败：{transcription['subtask_status']}")
                if 'message' in transcription:
                    print(f"错误信息：{transcription['message']}")
        
        # 生成时间戳，用于文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # 保存完整JSON结果
        json_file_path = os.path.join(results_dir, f"transcription_{timestamp}_full.json")
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=4)
        print(f"完整结果已保存到: {json_file_path}")
        
        # 保存纯文本结果
        text_file_path = os.path.join(results_dir, f"transcription_{timestamp}_text.txt")
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(all_text)
        print(f"文本内容已保存到: {text_file_path}")
        
        print('转写完成!')
    else:
        print(f"转写任务失败: {transcription_response.status_code}")
        print(f"错误信息: {transcription_response.output.message if hasattr(transcription_response.output, 'message') else '未知错误'}")
        
except Exception as e:
    print(f"发生异常: {str(e)}")
