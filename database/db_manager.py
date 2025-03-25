"""
数据库管理类
负责数据库连接和基本的CRUD操作
"""

import sqlite3
import os
import datetime
from pathlib import Path
from database.models import (
    CREATE_TASKS_TABLE, 
    CREATE_RESULTS_TABLE,
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED
)

class DatabaseManager:
    def __init__(self, db_path="db.sqlite"):
        """初始化数据库管理器"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.initialize_db()
    
    def connect(self):
        """连接到数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
        self.cursor = self.conn.cursor()
        return self.conn
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
    
    def initialize_db(self):
        """初始化数据库，创建必要的表"""
        conn = self.connect()
        try:
            # 创建任务表
            conn.execute(CREATE_TASKS_TABLE)
            # 创建结果表
            conn.execute(CREATE_RESULTS_TABLE)
            conn.commit()
        finally:
            self.close()
    
    # 任务相关操作
    def create_task(self, url=None, file_path=None, ocr_engine="local"):
        """创建新任务"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (url, file_path, status, ocr_engine)
                VALUES (?, ?, ?, ?)
                """,
                (url, file_path, TASK_STATUS_PENDING, ocr_engine)
            )
            conn.commit()
            return cursor.lastrowid  # 返回新创建任务的ID
        finally:
            self.close()
    
    def get_task(self, task_id):
        """获取任务信息"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks WHERE id = ?
                """,
                (task_id,)
            )
            task = cursor.fetchone()
            return dict(task) if task else None
        finally:
            self.close()
    
    def get_all_tasks(self):
        """获取所有任务"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks ORDER BY created_at DESC
                """
            )
            tasks = cursor.fetchall()
            return [dict(task) for task in tasks]
        finally:
            self.close()
    
    def get_pending_tasks(self):
        """获取待处理的任务"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC
                """,
                (TASK_STATUS_PENDING,)
            )
            tasks = cursor.fetchall()
            return [dict(task) for task in tasks]
        finally:
            self.close()
    
    def update_task_status(self, task_id, status, error_message=None):
        """更新任务状态"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks 
                SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, error_message, task_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.close()
    
    def update_task_file_path(self, task_id, file_path):
        """更新任务文件路径"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks 
                SET file_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (file_path, task_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.close()
    
    def delete_task(self, task_id):
        """删除任务"""
        conn = self.connect()
        try:
            # 先删除关联的结果
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM results WHERE task_id = ?
                """,
                (task_id,)
            )
            
            # 再删除任务
            cursor.execute(
                """
                DELETE FROM tasks WHERE id = ?
                """,
                (task_id,)
            )
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.close()
    
    # 结果相关操作
    def create_result(self, task_id, text_content, result_path=None):
        """创建OCR结果"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO results (task_id, text_content, result_path)
                VALUES (?, ?, ?)
                """,
                (task_id, text_content, result_path)
            )
            conn.commit()
            
            # 更新任务状态为已完成
            self.update_task_status(task_id, TASK_STATUS_COMPLETED)
            
            return cursor.lastrowid  # 返回新创建结果的ID
        finally:
            self.close()
    
    def get_result(self, result_id):
        """获取OCR结果"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM results WHERE id = ?
                """,
                (result_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            self.close()
    
    def get_results_by_task(self, task_id):
        """获取任务的OCR结果"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM results WHERE task_id = ?
                """,
                (task_id,)
            )
            results = cursor.fetchall()
            return [dict(result) for result in results]
        finally:
            self.close()
    
    def delete_result(self, result_id):
        """删除OCR结果"""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM results WHERE id = ?
                """,
                (result_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.close()
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
