"""
任务管理页面UI组件
显示任务列表和状态
"""

import streamlit as st
import pandas as pd
import time
from database.db_manager import DatabaseManager
from services.task_service import TaskService
from database.models import (
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED
)

def show_task_page():
    """显示任务管理页面"""
    st.title("任务管理")
    
    # 获取所有任务
    db = DatabaseManager()
    tasks = db.get_all_tasks()
    
    if not tasks:
        st.info("暂无任务")
        
        # 即使没有任务，也显示数据库维护选项
        show_database_maintenance()
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
            task = db.get_task(task_id)
            if task:
                task_service = TaskService()
                if task_service.delete_task(task_id):
                    st.success(f"任务 {task_id} 已删除")
                    st.rerun()  # 刷新页面
                else:
                    st.error(f"任务 {task_id} 删除失败")
            else:
                st.error(f"未找到ID为{task_id}的任务")
                
        elif action == "重试任务":
            task = db.get_task(task_id)
            if task:
                if task['status'] == TASK_STATUS_FAILED:
                    # 更新任务状态为待处理
                    db.update_task_status(task_id, TASK_STATUS_PENDING)
                    # 重新处理任务
                    task_service = TaskService()
                    if task_service.process_task(task_id):
                        st.success(f"任务 {task_id} 已重新提交处理")
                        st.rerun()  # 刷新页面
                    else:
                        st.error(f"任务 {task_id} 重试失败")
                else:
                    st.warning(f"只能重试失败的任务，当前任务状态为: {task['status']}")
            else:
                st.error(f"未找到ID为{task_id}的任务")

    # 批量操作功能
    st.subheader("批量操作")
    batch_action = st.selectbox(
        "选择批量操作",
        ["无操作", "批量删除已完成任务", "批量删除失败任务", "批量重试失败任务", "批量删除所有任务"]
    )

    # 使用会话状态来保存确认状态
    if "confirm_delete_all" not in st.session_state:
        st.session_state.confirm_delete_all = False

    # 根据选择的批量操作显示不同的按钮和确认机制
    if batch_action == "批量删除所有任务":
        # 使用两步确认机制
        st.warning("⚠️ 此操作将删除所有任务，且不可恢复！")
        
        # 第一步：显示确认复选框
        confirm = st.checkbox("我确认要删除所有任务", key="confirm_checkbox")
        
        # 第二步：如果勾选了确认框，显示最终确认按钮
        if confirm:
            if st.button("确认删除所有任务", type="primary"):
                task_service = TaskService()
                with st.spinner(f"正在删除所有{len(tasks)}个任务..."):
                    # 调用任务服务的批量删除方法
                    deleted_count = task_service.delete_all_tasks()
                    st.success(f"已删除所有{deleted_count}个任务")
                    # 重置确认状态
                    st.session_state.confirm_delete_all = False
                    time.sleep(1)  # 给用户一点时间看到成功消息
                    st.rerun()  # 刷新页面
    
    # 其他批量操作
    elif batch_action != "无操作" and st.button(f"执行{batch_action}"):
        task_service = TaskService()
        
        if batch_action == "批量删除已完成任务":
            completed_tasks = [task for task in tasks if task['status'] == TASK_STATUS_COMPLETED]
            if completed_tasks:
                with st.spinner(f"正在删除{len(completed_tasks)}个已完成任务..."):
                    success_count = 0
                    for task in completed_tasks:
                        if task_service.delete_task(task['id']):
                            success_count += 1
                    
                    st.success(f"已删除{success_count}/{len(completed_tasks)}个已完成任务")
                    time.sleep(1)  # 给用户一点时间看到成功消息
                    st.rerun()  # 刷新页面
            else:
                st.info("没有已完成的任务")
            
        elif batch_action == "批量删除失败任务":
            failed_tasks = [task for task in tasks if task['status'] == TASK_STATUS_FAILED]
            if failed_tasks:
                with st.spinner(f"正在删除{len(failed_tasks)}个失败任务..."):
                    success_count = 0
                    for task in failed_tasks:
                        if task_service.delete_task(task['id']):
                            success_count += 1
                    
                    st.success(f"已删除{success_count}/{len(failed_tasks)}个失败任务")
                    time.sleep(1)  # 给用户一点时间看到成功消息
                    st.rerun()  # 刷新页面
            else:
                st.info("没有失败的任务")
            
        elif batch_action == "批量重试失败任务":
            failed_tasks = [task for task in tasks if task['status'] == TASK_STATUS_FAILED]
            if failed_tasks:
                with st.spinner(f"正在重试{len(failed_tasks)}个失败任务..."):
                    success_count = 0
                    for task in failed_tasks:
                        # 更新任务状态为待处理
                        db.update_task_status(task['id'], TASK_STATUS_PENDING)
                        # 重新处理任务
                        if task_service.process_task(task['id']):
                            success_count += 1
                    
                    st.success(f"成功重试 {success_count}/{len(failed_tasks)} 个任务")
                    time.sleep(1)  # 给用户一点时间看到成功消息
                    st.rerun()  # 刷新页面
            else:
                st.info("没有失败的任务")
    
    # 显示数据库维护选项
    show_database_maintenance()

def show_database_maintenance():
    """显示数据库维护选项"""
    st.subheader("数据库维护")
    
    # 初始化会话状态
    if "db_maintenance_action" not in st.session_state:
        st.session_state.db_maintenance_action = "无操作"
    
    if "confirm_reset_db" not in st.session_state:
        st.session_state.confirm_reset_db = False
    
    # 选择维护操作
    maintenance_action = st.selectbox(
        "选择维护操作",
        ["无操作", "整理数据库", "优化数据库", "清理数据库缓存", "备份数据库", "重置数据库"],
        key="maintenance_action_select"
    )
    
    # 保存当前选择的操作到会话状态
    st.session_state.db_maintenance_action = maintenance_action
    
    # 处理重置数据库的特殊确认流程
    if maintenance_action == "重置数据库":
        st.warning("⚠️ 此操作将删除所有数据，且不可恢复！")
        
        # 第一步：显示确认复选框
        confirm = st.checkbox("我确认要重置数据库", key="confirm_reset_checkbox")
        
        # 保存确认状态到会话状态
        st.session_state.confirm_reset_db = confirm
        
        # 第二步：如果勾选了确认框，显示最终确认按钮
        if confirm:
            if st.button("确认重置数据库", type="primary", key="confirm_reset_button"):
                db = DatabaseManager()
                with st.spinner("正在重置数据库..."):
                    success = db.reset_database()
                    if success:
                        st.success("数据库已重置")
                        # 重置确认状态
                        st.session_state.confirm_reset_db = False
                        time.sleep(1)  # 给用户一点时间看到成功消息
                        st.rerun()  # 刷新页面
                    else:
                        st.error("数据库重置失败")
    
    # 处理其他维护操作
    elif maintenance_action != "无操作" and st.button(f"执行{maintenance_action}", key="execute_maintenance_button"):
        db = DatabaseManager()
        
        if maintenance_action == "整理数据库":
            with st.spinner("正在整理数据库..."):
                success = db.vacuum_database()
                if success:
                    st.success("数据库整理完成")
                else:
                    st.error("数据库整理失败")
        
        elif maintenance_action == "优化数据库":
            with st.spinner("正在优化数据库..."):
                success = db.optimize_database()
                if success:
                    st.success("数据库优化完成")
                else:
                    st.error("数据库优化失败")
        
        elif maintenance_action == "清理数据库缓存":
            with st.spinner("正在清理数据库缓存..."):
                success = db.clear_cache()
                if success:
                    st.success("数据库缓存清理完成")
                    time.sleep(1)  # 给用户一点时间看到成功消息
                    st.rerun()  # 刷新页面
                else:
                    st.error("数据库缓存清理失败")
        
        elif maintenance_action == "备份数据库":
            with st.spinner("正在备份数据库..."):
                backup_path = db.backup_database()
                if backup_path:
                    st.success(f"数据库已备份到: {backup_path}")
                else:
                    st.error("数据库备份失败")