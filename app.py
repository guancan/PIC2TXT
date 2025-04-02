"""
主程序入口
Streamlit应用
"""

import streamlit as st
import os
import config
from ui.pics_upload_page import show_home_page
from ui.result_page import show_result_page
from ui.task_page import show_task_page

# 确保数据目录存在
os.makedirs("data/downloads", exist_ok=True)
os.makedirs("data/results", exist_ok=True)
os.makedirs("data/images", exist_ok=True)  # 为图片提取创建目录

# 设置页面配置
st.set_page_config(
    page_title="图片文字识别工具",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 侧边栏导航
st.sidebar.title("功能菜单")
page = st.sidebar.radio("选择功能", ["CSV处理", "图片处理", "视频处理", "任务管理", "查看结果"])

# Mistral API密钥设置
mistral_api_key = st.sidebar.text_input("Mistral API密钥", 
                                        placeholder="可选，不填则使用默认配置", 
                                        type="password")
if mistral_api_key:
    os.environ["MISTRAL_API_KEY"] = mistral_api_key
    config.MISTRAL_API_KEY = mistral_api_key
    st.sidebar.success("Mistral API密钥已设置")

# 阿里云API密钥设置
ali_api_key = st.sidebar.text_input("阿里云Paraformer API密钥", 
                                   placeholder="可选，不填则使用默认配置", 
                                   type="password")
if ali_api_key:
    os.environ["ALI_PARAFORMER_API_KEY"] = ali_api_key
    config.ALI_PARAFORMER_API_KEY = ali_api_key
    st.sidebar.success("阿里云API密钥已设置")

# 渲染选中的页面
if page == "图片处理":
    show_home_page()
elif page == "视频处理":
    from ui.video_upload_page import show_video_page
    show_video_page()
elif page == "任务管理":
    show_task_page()
elif page == "查看结果":
    show_result_page()
elif page == "CSV处理":
    from ui.csv_page import show_csv_page
    show_csv_page()

# 添加页脚
st.sidebar.markdown("---")
st.sidebar.info("图片文字识别工具 v0.2")
