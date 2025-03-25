"""
主程序入口
Streamlit应用
"""

import streamlit as st
import os
import time
import pandas as pd
from services.task_service import TaskService

# 初始化服务
task_service = TaskService()

# 确保数据目录存在
os.makedirs("data/downloads", exist_ok=True)
os.makedirs("data/results", exist_ok=True)

# 设置页面配置
st.set_page_config(
    page_title="图片文字识别工具",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 侧边栏导航
st.sidebar.title("功能菜单")
page = st.sidebar.radio("选择功能", ["提交任务", "查看结果"])

# Mistral API密钥设置
mistral_api_key = st.sidebar.text_input("Mistral API密钥", type="password")
if mistral_api_key:
    os.environ["MISTRAL_API_KEY"] = mistral_api_key
    st.sidebar.success("API密钥已设置")

# 渲染选中的页面
if page == "提交任务":
    st.header("提交新任务")
    
    # 输入URL
    url = st.text_input("输入图片或PDF的URL")
    
    # 选择OCR引擎
    ocr_engine = st.radio("选择OCR引擎", ["本地PaddleOCR", "Mistral AI OCR"])
    
    # 映射OCR引擎选择
    engine_map = {
        "本地PaddleOCR": "local",
        "Mistral AI OCR": "mistral"
    }
    
    # 如果选择了Mistral但没有设置API密钥，显示警告
    if ocr_engine == "Mistral AI OCR" and not mistral_api_key:
        st.warning("请在侧边栏设置Mistral API密钥")
    
    # 提交按钮
    if st.button("提交任务"):
        if not url:
            st.error("请输入URL")
        elif ocr_engine == "Mistral AI OCR" and not mistral_api_key:
            st.error("使用Mistral AI OCR需要设置API密钥")
        else:
            with st.spinner("正在提交任务..."):
                # 创建任务
                task_id = task_service.create_task(url, ocr_engine=engine_map[ocr_engine])
                
                # 开始处理任务
                success = task_service.process_task(task_id)
                
                if success:
                    st.success(f"任务处理成功! 任务ID: {task_id}")
                    st.info("您可以在'查看结果'页面查看处理结果")
                else:
                    task = task_service.get_task(task_id)
                    st.error(f"任务处理失败: {task.get('error_message', '未知错误')}")

# 查看结果页面
elif page == "查看结果":
    st.header("查看任务结果")
    
    # 获取所有任务
    tasks = task_service.get_all_tasks()
    
    if not tasks:
        st.info("暂无任务")
    else:
        # 显示任务列表
        st.subheader("任务列表")
        
        # 创建任务表格
        task_data = []
        for task in tasks:
            task_id = task["id"]
            url = task["url"]
            status = task["status"]
            created_at = task["created_at"]
            ocr_engine = task.get("ocr_engine", "local")
            engine_display = "本地PaddleOCR" if ocr_engine == "local" else "Mistral AI OCR"
            
            task_data.append({
                "ID": task_id,
                "URL": url,
                "状态": status,
                "创建时间": created_at,
                "OCR引擎": engine_display
            })
        
        # 显示任务表格
        task_df = pd.DataFrame(task_data)
        st.dataframe(task_df)
        
        # 选择任务查看详情
        selected_task_id = st.selectbox("选择任务ID查看详情", [task["id"] for task in tasks])
        
        if selected_task_id:
            # 获取任务详情
            task = task_service.get_task(selected_task_id)
            result = task_service.get_task_result(selected_task_id)
            
            # 显示任务详情
            st.subheader(f"任务 #{selected_task_id} 详情")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**URL:** {task['url']}")
                st.write(f"**状态:** {task['status']}")
                st.write(f"**创建时间:** {task['created_at']}")
                st.write(f"**OCR引擎:** {'本地PaddleOCR' if task.get('ocr_engine') == 'local' else 'Mistral AI OCR'}")
            
            with col2:
                if task["file_path"]:
                    st.write(f"**文件路径:** {task['file_path']}")
                    
                    # 如果是图片，显示图片
                    file_ext = os.path.splitext(task["file_path"])[1].lower()
                    if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                        st.image(task["file_path"], caption="下载的图片")
            
            # 显示错误信息（如果有）
            if task["status"] == "failed" and task.get("error_message"):
                st.error(f"错误信息: {task['error_message']}")
            
            # 显示OCR结果
            if result:
                st.subheader("OCR识别结果")
                
                # 显示文本内容
                with st.expander("查看文本内容", expanded=True):
                    st.text_area("识别的文本", result["text_content"], height=300)
                
                # 提供下载链接
                if os.path.exists(result["result_path"]):
                    with open(result["result_path"], "r", encoding="utf-8") as f:
                        st.download_button(
                            label="下载文本文件",
                            data=f,
                            file_name=os.path.basename(result["result_path"]),
                            mime="text/plain"
                        )

# 添加页脚
st.sidebar.markdown("---")
st.sidebar.info("图片文字识别工具 v0.1")
