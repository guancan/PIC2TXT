"""
结果展示页面UI组件
显示OCR处理结果
"""

import os
import streamlit as st
import pandas as pd
from database.db_manager import DatabaseManager
import config

def show_result_page():
    """显示结果页面"""
    st.title("OCR结果查看")
    
    # 获取所有任务
    db = DatabaseManager()
    tasks = db.get_all_tasks()
    
    # 过滤出已完成的任务
    completed_tasks = [task for task in tasks if task['status'] == 'completed']
    
    if not completed_tasks:
        st.info("暂无已完成的任务")
        return
    
    # 创建任务选择器
    task_options = {f"任务 #{task['id']} - {task['url'][:30] if task['url'] else task['file_path'][:30]}...": task['id'] for task in completed_tasks}
    selected_task_name = st.selectbox("选择已完成的任务", list(task_options.keys()))
    selected_task_id = task_options[selected_task_name]
    
    # 获取任务详情
    task = db.get_task(selected_task_id)
    results = db.get_results_by_task(selected_task_id)
    
    if not task or not results:
        st.warning("无法获取任务结果")
        return
    
    # 显示任务详情
    st.subheader("任务详情")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**任务ID:** {task['id']}")
        if task.get('url'):
            st.write(f"**URL:** {task['url']}")
        st.write(f"**创建时间:** {task['created_at']}")
    
    with col2:
        st.write(f"**状态:** {task['status']}")
        st.write(f"**OCR引擎:** {'本地PaddleOCR' if task.get('ocr_engine') == 'local' else 'Mistral AI OCR'}")
        if task.get('file_path'):
            st.write(f"**文件路径:** {task['file_path']}")
    
    # 显示OCR结果
    st.subheader("OCR结果")
    result = results[0]  # 获取第一个结果
    
    # 显示文本内容
    with st.expander("文本内容", expanded=True):
        st.text_area("识别的文本", result["text_content"], height=300)
    
    # 提供下载链接
    if os.path.exists(result["result_path"]):
        with open(result["result_path"], "rb") as file:
            st.download_button(
                label="下载文本文件",
                data=file,
                file_name=os.path.basename(result["result_path"]),
                mime="text/plain"
            )
    
    # 显示原始图片（如果有）
    if task.get('file_path') and os.path.exists(task['file_path']):
        file_ext = os.path.splitext(task['file_path'])[1].lower()
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            st.subheader("原始图片")
            st.image(task['file_path'], caption="原始图片")