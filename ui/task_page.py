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
    
    # 初始化数据库和任务服务
    db = DatabaseManager()
    task_service = TaskService()
    
    # 获取所有任务
    try:
        tasks = db.get_all_tasks()
        st.write(f"共找到 {len(tasks)} 个任务")
    except Exception as e:
        st.error(f"获取任务失败: {str(e)}")
        tasks = []
    
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
        tasks_df['状态'] = tasks_df['status'].apply(get_status_icon)
    
    # 选择要显示的列
    display_columns = ['id', '状态', 'url', 'file_path', 'created_at', 'updated_at']
    display_columns = [col for col in display_columns if col in tasks_df.columns]
    
    # 重命名列
    column_names = {
        'id': '任务ID',
        'url': 'URL',
        'file_path': '文件路径',
        'created_at': '创建时间',
        'updated_at': '更新时间'
    }
    
    # 只重命名存在的列
    rename_dict = {k: v for k, v in column_names.items() if k in tasks_df.columns}
    tasks_df = tasks_df.rename(columns=rename_dict)
    
    # 显示任务表格
    st.dataframe(tasks_df[['任务ID', '状态'] + [rename_dict.get(col, col) for col in display_columns if col not in ['id', '状态']]])
    
    # 任务操作部分
    st.subheader("任务操作")
    
    # 输入任务ID
    task_id_input = st.text_input("输入任务ID", key="task_id_input")
    
    # 选择操作
    col1, col2 = st.columns(2)
    
    with col1:
        operation = st.selectbox(
            "选择操作",
            ["查看详情", "重新处理", "删除任务"],
            key="task_operation_select"
        )
    
    with col2:
        if st.button("执行", key="execute_task_operation_button"):
            if not task_id_input:
                st.warning("请输入任务ID")
            else:
                try:
                    task_id = int(task_id_input)
                    task = db.get_task(task_id)
                    
                    if not task:
                        st.error(f"任务 #{task_id} 不存在")
                    else:
                        if operation == "查看详情":
                            st.json(task)
                            
                            # 如果任务已完成，显示结果
                            if task['status'] == TASK_STATUS_COMPLETED:
                                results = db.get_results_by_task(task_id)
                                if results:
                                    st.subheader("OCR结果")
                                    st.text_area("文本内容", results[0]['text_content'], height=200)
                        
                        elif operation == "重新处理":
                            # 更新任务状态为待处理
                            db.update_task_status(task_id, TASK_STATUS_PENDING)
                            # 重新处理任务
                            with st.spinner("正在处理任务..."):
                                if task_service.process_task(task_id):
                                    st.success(f"任务 #{task_id} 处理成功")
                                    time.sleep(1)  # 给用户一点时间看到成功消息
                                    st.rerun()  # 刷新页面
                                else:
                                    st.error(f"任务 #{task_id} 处理失败")
                        
                        elif operation == "删除任务":
                            if st.button("确认删除", key="confirm_delete_button"):
                                with st.spinner("正在删除任务..."):
                                    if task_service.delete_task(task_id):
                                        st.success(f"任务 #{task_id} 已删除")
                                        time.sleep(1)  # 给用户一点时间看到成功消息
                                        st.rerun()  # 刷新页面
                                    else:
                                        st.error(f"删除任务 #{task_id} 失败")
                except ValueError:
                    st.error("任务ID必须是数字")
    
    # 批量操作部分
    st.subheader("批量操作")
    
    # 选择批量操作
    batch_operation = st.selectbox(
        "选择批量操作",
        ["无操作", "删除所有任务", "重试所有失败任务"],
        key="batch_operation_select"
    )
    
    # 保存当前选择的操作到会话状态
    st.session_state.batch_operation = batch_operation
    
    # 处理删除所有任务的特殊确认流程
    if batch_operation == "删除所有任务":
        st.warning("⚠️ 此操作将删除所有任务，且不可恢复！")
        
        # 第一步：显示确认复选框
        confirm = st.checkbox("我确认要删除所有任务", key="confirm_delete_all_checkbox")
        
        # 保存确认状态到会话状态
        st.session_state.confirm_delete_all = confirm
        
        # 第二步：如果勾选了确认框，显示最终确认按钮
        if confirm:
            if st.button("确认删除所有任务", type="primary", key="confirm_delete_all_button"):
                with st.spinner("正在删除所有任务..."):
                    deleted_count = task_service.delete_all_tasks()
                    st.success(f"已删除 {deleted_count} 个任务")
                    # 重置确认状态
                    st.session_state.confirm_delete_all = False
                    time.sleep(1)  # 给用户一点时间看到成功消息
                    st.rerun()  # 刷新页面
    
    # 处理重试所有失败任务
    elif batch_operation == "重试所有失败任务" and st.button("执行重试所有失败任务", key="retry_all_failed_button"):
        # 获取所有任务
        tasks = db.get_all_tasks()
        # 过滤出失败的任务
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
        if "confirm_reset_db" not in st.session_state:
            st.session_state.confirm_reset_db = False
        
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

    # 添加数据库修复按钮
    if st.button("修复数据库", key="fix_database_button"):
        fix_database()

def fix_database():
    """修复数据库"""
    db = DatabaseManager()
    result = db.fix_database()
    
    if result:
        st.success("数据库修复成功！请重启应用程序。")
    else:
        st.error("数据库修复失败，请查看日志获取详细信息。")