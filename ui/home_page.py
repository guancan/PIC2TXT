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

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def show_home_page():
    """显示首页"""
    st.title("图片/PDF文字识别")
    
    # 创建服务实例
    download_service = DownloadService(config.DOWNLOAD_DIR)
    task_service = TaskService()
    
    # URL输入
    url = st.text_input("输入图片或PDF的URL")
    
    # OCR引擎选择
    ocr_engine = st.selectbox(
        "选择OCR引擎",
        ["local", "mistral"],
        format_func=lambda x: "本地PaddleOCR" if x == "local" else "Mistral AI OCR"
    )
    
    if st.button("开始处理"):
        if url:
            with st.spinner("正在处理..."):
                # 创建任务
                task_id = task_service.create_task(url, ocr_engine=ocr_engine)
                
                # 处理任务
                success = task_service.process_task(task_id)
                
                if success:
                    # 获取任务结果
                    result = task_service.get_task_result(task_id)
                    
                    if result:
                        st.success("处理成功!")
                        
                        # 显示结果
                        with st.expander("识别结果", expanded=True):
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
        else:
            st.warning("请输入URL")
    
    # 显示任务列表
    with st.expander("任务列表", expanded=False):
        tasks = task_service.get_all_tasks()
        
        if tasks:
            for task in tasks:
                status_color = {
                    "pending": "🟡",
                    "processing": "🔵",
                    "completed": "🟢",
                    "failed": "🔴"
                }.get(task["status"], "⚪")
                
                st.write(f"{status_color} 任务ID: {task['id']} - 状态: {task['status']} - URL: {task['url']}")
                
                if task["status"] == "completed":
                    if st.button(f"查看结果 #{task['id']}", key=f"view_{task['id']}"):
                        result = task_service.get_task_result(task["id"])
                        if result:
                            st.text_area(f"任务 #{task['id']} 结果", result["text_content"], height=200)
        else:
            st.write("暂无任务")
    
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
