"""
视频处理页面UI组件
提供视频URL输入和字幕提取功能
"""

import os
import streamlit as st
import logging
from services.task_service import TaskService
import config

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 视频引擎常量 - 后续会移到models.py中
VIDEO_ENGINE_ALI_PARAFORMER = "ali_paraformer_v2"

def show_video_page():
    """显示视频处理页面"""
    st.title("视频字幕提取")
    
    # 创建服务实例
    task_service = TaskService()
    
    # URL输入 - 文本区域，支持多行输入
    urls_input = st.text_area("输入视频URL（每行一个URL）", height=150)
    
    # 视频处理参数配置
    with st.expander("高级设置", expanded=False):
        # 说话人分离开关 - 默认关闭
        diarization_enabled = st.checkbox("启用说话人分离", value=False, 
                                        help="启用后可以区分不同说话人的内容")
        
        # 说话人数量设置 - 仅当启用说话人分离时显示
        speaker_count = None
        if diarization_enabled:
            speaker_count_enabled = st.checkbox("指定说话人数量", value=False,
                                            help="不指定时，系统将自动判断说话人数量")
            if speaker_count_enabled:
                speaker_count = st.slider("说话人数量", min_value=2, max_value=100, value=3, 
                                        help="设置视频中预计的说话人数量，有助于提高识别准确率")
        
        # 语言选择 - 根据API文档支持的语言
        languages = st.multiselect(
            "语言选择",
            options=["中文", "英文", "日语", "韩语", "德语", "法语", "俄语", "粤语"],
            default=["中文", "英文"],  # 默认选择中文和英文，与API默认值一致
            help="选择视频中可能出现的语言，支持多语言混合识别"
        )
        
        # 语言代码映射
        language_codes = {
            "中文": "zh",
            "英文": "en",
            "日语": "ja",
            "韩语": "ko",
            "德语": "de",
            "法语": "fr",
            "俄语": "ru",
            "粤语": "yue"
        }
        
        # 转换为API需要的语言代码
        language_hints = [language_codes[lang] for lang in languages if lang in language_codes]
        
        # 如果用户没有选择任何语言，使用API默认值
        if not language_hints:
            language_hints = ["zh", "en"]
    
    # 视频引擎选择
    video_engine = st.selectbox(
        "视频处理引擎",
        options=[VIDEO_ENGINE_ALI_PARAFORMER],
        format_func=lambda x: "阿里云Paraformer V2 (推荐)" if x == VIDEO_ENGINE_ALI_PARAFORMER else x,
        help="目前仅支持阿里云Paraformer V2引擎"
    )
    
    # 本地文件上传
    st.subheader("或上传本地视频文件")
    uploaded_file = st.file_uploader(
        "选择视频文件", 
        type=["mp4", "avi", "mov", "flv", "mkv", "wmv", "mp3", "wav", "aac", "flac", "m4a", "ogg", "opus"],
        help="支持常见视频和音频格式"
    )
    
    # 处理逻辑
    file_path = None
    if uploaded_file is not None:
        # 保存上传的文件
        file_path = os.path.join("data/uploads", uploaded_file.name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"文件 '{uploaded_file.name}' 上传成功!")
    
    # 处理按钮
    if st.button("处理视频URL"):
        if not config.ALI_PARAFORMER_API_KEY:
            st.error("未设置阿里云Paraformer API密钥，无法处理视频")
        elif not urls_input.strip():
            st.error("请输入至少一个视频URL")
        else:
            # 分割多行URL输入
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            
            if not urls:
                st.error("未检测到有效的URL")
            else:
                with st.spinner("正在提交视频处理任务..."):
                    try:
                        # 准备参数字典
                        params = {
                            "language_hints": language_hints,
                            "diarization_enabled": diarization_enabled
                        }
                        
                        # 仅当启用说话人分离且指定了说话人数量时，添加speaker_count参数
                        if diarization_enabled and speaker_count:
                            params["speaker_count"] = speaker_count
                        
                        # 处理每个URL
                        task_ids = []
                        for url in urls:
                            # 验证URL
                            from utils.video_utils import is_valid_video_url
                            if not is_valid_video_url(url):
                                st.warning(f"URL格式不正确或不支持: {url}")
                                continue
                            
                            # 创建视频任务
                            task_id = task_service.create_video_task(
                                url=url, 
                                video_engine=video_engine,
                                params=params
                            )
                            task_ids.append(task_id)
                            
                            # 立即开始处理任务
                            st.info(f"开始处理任务 ID: {task_id}...")
                            # 使用后台线程处理任务，避免阻塞UI
                            import threading
                            thread = threading.Thread(
                                target=task_service.process_video_task,
                                args=(task_id,)
                            )
                            thread.daemon = True
                            thread.start()
                        
                        if task_ids:
                            st.success(f"已提交 {len(task_ids)} 个视频处理任务!")
                            st.info(f"任务ID: {', '.join(map(str, task_ids))}")
                            st.info("视频处理已在后台开始，可能需要较长时间，请稍后在'任务管理'页面查看结果")
                        else:
                            st.error("没有成功提交任何任务")
                        
                    except Exception as e:
                        st.error(f"提交任务异常: {str(e)}")
    
    # 任务状态查询部分
    st.subheader("查询任务状态")
    task_id_input = st.text_input("输入任务ID")
    
    if st.button("查询状态"):
        if not task_id_input:
            st.warning("请输入任务ID")
        else:
            try:
                task_id = int(task_id_input)
                # 假设task_service.get_video_task_status方法已实现
                task_status = task_service.get_task_status(task_id)
                
                if task_status:
                    status = task_status.get("status", "未知")
                    st.info(f"任务状态: {status}")
                    
                    # 如果任务已完成，显示结果链接
                    if status == "completed":
                        # 假设task_service.get_video_task_result方法已实现
                        result = task_service.get_task_result(task_id)
                        if result:
                            st.success("处理完成!")
                            
                            # 显示结果
                            with st.expander("字幕内容", expanded=True):
                                st.text_area("文本内容", result.get("text_content", ""), height=300)
                                
                                # 提供下载链接
                                result_path = result.get("result_path", "")
                                if result_path and os.path.exists(result_path):
                                    with open(result_path, "rb") as file:
                                        st.download_button(
                                            label="下载字幕文件",
                                            data=file,
                                            file_name=os.path.basename(result_path),
                                            mime="text/plain"
                                        )
                    elif status == "processing":
                        st.warning("任务正在处理中，请稍后再查询")
                    elif status == "failed":
                        error_message = task_status.get("error_message", "未知错误")
                        st.error(f"任务处理失败: {error_message}")
                else:
                    st.error(f"未找到任务ID: {task_id}")
            except ValueError:
                st.error("任务ID必须是数字")
            except Exception as e:
                st.error(f"查询异常: {str(e)}") 