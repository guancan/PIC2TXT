"""
任务管理页面UI组件
显示任务列表和状态
"""

import streamlit as st
import pandas as pd
from database.db_manager import DatabaseManager
from database.models import (
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED
)

def render():
    st.title("任务管理")
    
    # 获取所有任务
    db = DatabaseManager()
    tasks = db.get_all_tasks()
    
    if not tasks:
        st.info("暂无任务")
        return
    
    # 创建任务数据框
    tasks_df = pd.DataFrame(tasks)
    
    # 格式化时间列
    if 'created_at' in tasks_df.columns:
        tasks_df['created_at'] = pd.to_datetime(tasks_df['created_at'])
        tasks_df['created_at'] = tasks_df['created_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    if 'updated_at' in tasks_df.columns:
        tasks_df['updated_at'] = pd.to_datetime(tasks_df['updated_at'])
        tasks_df['updated_at'] = tasks_df['updated_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 添加状态图标
    def get_status_icon(status):
        if status == TASK_STATUS_PENDING:
            return "⏳"
        elif status == TASK_STATUS_PROCESSING:
            return "🔄"
        elif status == TASK_STATUS_COMPLETED:
            return "✅"
        elif status == TASK_STATUS_FAILED:
            return "❌"
        else:
            return "❓"
    
    if 'status' in tasks_df.columns:
        tasks_df['状态'] = tasks_df['status'].apply(get_status_icon) + " " + tasks_df['status']
    
    # 显示任务表格
    st.dataframe(
        tasks_df[['id', 'url', 'file_path', '状态', 'created_at', 'updated_at']],
        column_config={
            'id': '任务ID',
            'url': 'URL',
            'file_path': '文件路径',
            'created_at': '创建时间',
            'updated_at': '更新时间'
        },
        hide_index=True
    )
    
    # 任务操作
    st.subheader("任务操作")
    
    col1, col2 = st.columns(2)
    
    with col1:
        task_id = st.number_input("输入任务ID", min_value=1, step=1)
    
    with col2:
        action = st.selectbox(
            "选择操作",
            ["查看详情", "删除任务", "重试任务"]
        )
    
    if st.button("执行"):
        if action == "查看详情":
            task = db.get_task(task_id)
            if task:
                st.json(task)
                
                # 显示任务结果
                results = db.get_results_by_task(task_id)
                if results:
                    st.subheader("任务结果")
                    for result in results:
                        st.json(result)
                else:
                    st.info("该任务暂无结果")
            else:
                st.error(f"未找到ID为{task_id}的任务")
                
        elif action == "删除任务":
            try:
                db.delete_task(task_id)
                st.success(f"已删除任务 {task_id}")
            except Exception as e:
                st.error(f"删除任务失败: {str(e)}")
                
        elif action == "重试任务":
            # 这里将实现重试任务的逻辑
            st.info("重试功能将在后续实现")
