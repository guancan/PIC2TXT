"""
CSV处理页面
提供CSV表格上传、处理和下载功能
"""

import os
import streamlit as st
import pandas as pd
from typing import Optional, Tuple
import time

from services.csv_service import CSVService
from database.db_manager import DatabaseManager
import config

def show_csv_page():
    """渲染CSV处理页面"""
    st.title("CSV表格处理")
    
    # 初始化服务
    db_manager = DatabaseManager(config.DB_PATH)
    csv_service = CSVService(db_manager=db_manager)
    
    # 创建两个标签页：上传处理和查看结果
    tab1, tab2 = st.tabs(["上传处理", "查看结果"])
    
    with tab1:
        render_upload_tab(csv_service)
    
    with tab2:
        render_results_tab(csv_service)

def render_upload_tab(csv_service: CSVService):
    """渲染上传处理标签页"""
    st.header("上传CSV文件")
    st.write("上传包含小红书笔记链接和图片链接的CSV文件，系统将自动处理并提取文本内容。")
    
    # 文件上传
    uploaded_file = st.file_uploader("选择CSV文件", type=["csv"], help="CSV文件必须包含note_url和image_list列")
    
    # OCR引擎选择
    ocr_engine = st.selectbox(
        "选择OCR引擎",
        options=["mistral", "local", "nlp"],
        format_func=lambda x: {
            "mistral": "Mistral AI OCR (推荐)",
            "local": "本地PaddleOCR",
            "nlp": "Mistral AI NLP"
        }.get(x, x),
        help="选择用于处理图片的OCR引擎"
    )
    
    # 处理按钮
    if uploaded_file is not None:
        if st.button("开始处理"):
            # 保存上传的文件
            temp_file_path = os.path.join(config.TEMP_DIR, uploaded_file.name)
            os.makedirs(config.TEMP_DIR, exist_ok=True)
            
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # 显示进度条
            with st.spinner("正在处理CSV文件..."):
                # 处理CSV文件
                success, message, output_file = csv_service.process_csv_file(temp_file_path, ocr_engine)
                
                if success:
                    st.success(message)
                    
                    # 显示处理结果预览
                    if output_file and os.path.exists(output_file):
                        try:
                            df = pd.read_csv(output_file)
                            st.write("处理结果预览:")
                            st.dataframe(df.head(10))
                            
                            # 提供下载链接
                            with open(output_file, "rb") as file:
                                st.download_button(
                                    label="下载处理后的CSV文件",
                                    data=file,
                                    file_name=os.path.basename(output_file),
                                    mime="text/csv"
                                )
                        except Exception as e:
                            st.error(f"预览结果时出错: {str(e)}")
                else:
                    st.error(message)
    
    # 使用说明
    with st.expander("CSV文件格式说明"):
        st.write("""
        CSV文件必须包含以下列:
        - **note_url**: 小红书笔记URL
        - **image_list**: 图片URL列表，多个URL用逗号分隔
        
        系统将自动添加以下列:
        - **image_txt**: OCR识别的文本内容
        """)
        
        # 示例数据
        example_data = {
            "note_url": ["https://www.xiaohongshu.com/note/123456", "https://www.xiaohongshu.com/note/789012"],
            "image_list": ["https://example.com/img1.jpg,https://example.com/img2.jpg", "https://example.com/img3.jpg"]
        }
        example_df = pd.DataFrame(example_data)
        st.write("示例数据:")
        st.dataframe(example_df)

def render_results_tab(csv_service: CSVService):
    """渲染查看结果标签页"""
    st.header("查看和更新结果")
    st.write("上传已处理的CSV文件，获取最新的OCR结果。")
    
    # 文件上传
    uploaded_file = st.file_uploader("选择已处理的CSV文件", type=["csv"], key="result_file_uploader", 
                                    help="上传之前处理过的CSV文件，系统将更新OCR结果")
    
    # 更新按钮
    if uploaded_file is not None:
        if st.button("更新OCR结果"):
            # 保存上传的文件
            temp_file_path = os.path.join(config.TEMP_DIR, uploaded_file.name)
            os.makedirs(config.TEMP_DIR, exist_ok=True)
            
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # 显示进度条
            with st.spinner("正在更新OCR结果..."):
                # 更新CSV文件
                success, message, output_file = csv_service.update_csv_with_results(temp_file_path)
                
                if success:
                    st.success(message)
                    
                    # 显示更新结果预览
                    if output_file and os.path.exists(output_file):
                        try:
                            df = pd.read_csv(output_file)
                            st.write("更新结果预览:")
                            st.dataframe(df.head(10))
                            
                            # 提供下载链接
                            with open(output_file, "rb") as file:
                                st.download_button(
                                    label="下载更新后的CSV文件",
                                    data=file,
                                    file_name=os.path.basename(output_file),
                                    mime="text/csv"
                                )
                        except Exception as e:
                            st.error(f"预览结果时出错: {str(e)}")
                else:
                    st.error(message)
    
    # 查找最近处理的文件
    st.subheader("最近处理的文件")
    
    # 获取结果目录中的CSV文件
    csv_files = []
    if os.path.exists(config.RESULT_DIR):
        for file in os.listdir(config.RESULT_DIR):
            if file.endswith(".csv"):
                file_path = os.path.join(config.RESULT_DIR, file)
                csv_files.append({
                    "name": file,
                    "path": file_path,
                    "time": os.path.getmtime(file_path)
                })
    
    # 按修改时间排序
    csv_files.sort(key=lambda x: x["time"], reverse=True)
    
    if csv_files:
        for i, file_info in enumerate(csv_files[:5]):  # 只显示最近5个文件
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{i+1}. {file_info['name']} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_info['time']))})")
            with col2:
                with open(file_info["path"], "rb") as f:
                    st.download_button(
                        label="下载",
                        data=f,
                        file_name=file_info["name"],
                        mime="text/csv",
                        key=f"download_{i}"
                    )
    else:
        st.write("没有找到处理过的CSV文件")

if __name__ == "__main__":
    show_csv_page() 