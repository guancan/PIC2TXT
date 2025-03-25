"""
首页UI组件
提供URL输入和OCR处理功能
"""

import os
import streamlit as st
import logging
from services.download_service import DownloadService
from services.ocr_factory import OCRFactory
from services.task_service import TaskService
import config
from database.models import OCR_ENGINE_LOCAL, OCR_ENGINE_MISTRAL, OCR_ENGINE_NLP

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def show_home_page():
    """显示首页"""
    st.title("图片/PDF文字识别")
    
    # 创建服务实例
    task_service = TaskService()
    
    # URL输入 - 修改为文本区域，支持多行输入
    urls_input = st.text_area("输入图片或PDF的URL（每行一个URL）", height=150)
    
    # 添加处理模式选择
    process_mode = st.radio(
        "选择处理模式",
        ["OCR识别", "自然语言分析"],
        index=0,
        help="OCR识别：提取图片中的文字内容；自然语言分析：使用AI分析并描述图片内容"
    )
    
    # OCR引擎选择 - 根据处理模式调整选项
    if process_mode == "OCR识别":
        ocr_engine = st.selectbox(
            "选择OCR引擎",
            [OCR_ENGINE_LOCAL, OCR_ENGINE_MISTRAL],
            index=1,  # 默认选中mistral
            format_func=lambda x: "本地PaddleOCR" if x == OCR_ENGINE_LOCAL else "Mistral AI OCR"
        )
    else:  # 自然语言分析模式
        ocr_engine = OCR_ENGINE_NLP
        st.info("自然语言分析模式将使用Mistral AI进行图片内容的智能分析")
    
    if st.button("开始处理"):
        if not urls_input:
            st.warning("请输入至少一个URL")
        else:
            # 分割多行URL
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            
            if not urls:
                st.warning("请输入有效的URL")
            else:
                with st.spinner(f"正在处理{len(urls)}个任务..."):
                    # 创建进度条
                    progress_bar = st.progress(0)
                    
                    # 批量处理URL
                    successful_tasks = 0
                    failed_tasks = 0
                    task_ids = []
                    
                    for i, url in enumerate(urls):
                        try:
                            # 创建任务
                            task_id = task_service.create_task(url, ocr_engine=ocr_engine)
                            task_ids.append(task_id)
                            
                            # 处理任务
                            success = task_service.process_task(task_id)
                            
                            if success:
                                successful_tasks += 1
                            else:
                                failed_tasks += 1
                                st.error(f"URL '{url}' 处理失败")
                        except Exception as e:
                            failed_tasks += 1
                            st.error(f"URL '{url}' 处理异常: {str(e)}")
                        
                        # 更新进度条
                        progress_bar.progress((i + 1) / len(urls))
                    
                    # 显示处理结果
                    if successful_tasks > 0:
                        st.success(f"成功处理 {successful_tasks} 个任务")
                        
                        # 如果只有一个成功的任务，直接显示结果
                        if successful_tasks == 1 and len(task_ids) == 1:
                            result = task_service.get_task_result(task_ids[0])
                            if result:
                                with st.expander("识别结果", expanded=True):
                                    if process_mode == "自然语言分析":
                                        st.markdown(result["text_content"])
                                    else:
                                        st.text_area("文本内容", result["text_content"], height=300)
                                    
                                    # 提供下载链接
                                    if os.path.exists(result["result_path"]):
                                        with open(result["result_path"], "rb") as file:
                                            st.download_button(
                                                label="下载文本文件",
                                                data=file,
                                                file_name=os.path.basename(result["result_path"]),
                                                mime="text/plain"
                                            )
                
                    if failed_tasks > 0:
                        st.warning(f"失败 {failed_tasks} 个任务")
    
    # 上传本地文件
    st.subheader("或者上传本地文件")
    uploaded_file = st.file_uploader("选择图片或PDF文件", type=["jpg", "jpeg", "png", "pdf"])
    
    if uploaded_file is not None:
        # 保存上传的文件
        file_path = os.path.join(config.DOWNLOAD_DIR, uploaded_file.name)
        os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"文件已上传: {uploaded_file.name}")
        
        # 处理上传的文件
        if st.button("处理上传的文件"):
            with st.spinner("正在处理..."):
                # 创建任务
                task_id = task_service.create_task(file_path=file_path, ocr_engine=ocr_engine)
                
                # 处理任务
                success = task_service.process_task(task_id)
                
                if success:
                    # 获取任务结果
                    result = task_service.get_task_result(task_id)
                    
                    if result:
                        st.success("处理成功!")
                        
                        # 显示结果
                        with st.expander("识别结果", expanded=True):
                            if process_mode == "自然语言分析":
                                st.markdown(result["text_content"])
                            else:
                                st.text_area("文本内容", result["text_content"], height=300)
                            
                            # 提供下载链接
                            if os.path.exists(result["result_path"]):
                                with open(result["result_path"], "rb") as file:
                                    st.download_button(
                                        label="下载文本文件",
                                        data=file,
                                        file_name=os.path.basename(result["result_path"]),
                                        mime="text/plain"
                                    )
                    else:
                        st.error("获取结果失败")
                else:
                    st.error("处理失败")