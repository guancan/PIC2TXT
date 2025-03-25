"""
数据库管理类
负责数据库连接和基本的CRUD操作
"""

import sqlite3
import os
import datetime
import logging
import shutil
from pathlib import Path
from database.models import (
    CREATE_TASKS_TABLE, 
    CREATE_RESULTS_TABLE,
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED
)

# 设置日志
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path="db.sqlite"):
        """初始化数据库管理器"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.initialize_db()
    
    def connect(self):
        """连接到数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # 启用外键约束
            self.conn.execute("PRAGMA foreign_keys = ON")
            # 设置超时时间
            self.conn.execute("PRAGMA busy_timeout = 5000")
            # 设置同步模式为NORMAL (1)，提高性能
            self.conn.execute("PRAGMA synchronous = 1")
            # 设置日志模式为WAL，提高性能和可靠性
            self.conn.execute("PRAGMA journal_mode = WAL")
            
            self.conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
            self.cursor = self.conn.cursor()
            return self.conn
        except sqlite3.Error as e:
            logger.error(f"数据库连接错误: {str(e)}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.close()
            except sqlite3.Error as e:
                logger.error(f"关闭数据库连接错误: {str(e)}")
            finally:
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
        except sqlite3.Error as e:
            logger.error(f"初始化数据库错误: {str(e)}")
            conn.rollback()
            raise
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
        except sqlite3.Error as e:
            logger.error(f"创建任务错误: {str(e)}")
            conn.rollback()
            raise
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
        except sqlite3.Error as e:
            logger.error(f"获取任务错误: {str(e)}")
            raise
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
        except sqlite3.Error as e:
            logger.error(f"获取所有任务错误: {str(e)}")
            raise
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
        except sqlite3.Error as e:
            logger.error(f"获取待处理任务错误: {str(e)}")
            raise
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
        except sqlite3.Error as e:
            logger.error(f"更新任务状态错误: {str(e)}")
            conn.rollback()
            raise
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
        except sqlite3.Error as e:
            logger.error(f"更新任务文件路径错误: {str(e)}")
            conn.rollback()
            raise
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
            logger.info(f"成功删除任务 ID: {task_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"删除任务错误 ID: {task_id}, 错误: {str(e)}")
            conn.rollback()
            raise
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
        except sqlite3.Error as e:
            logger.error(f"创建结果错误: {str(e)}")
            conn.rollback()
            raise
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
        except sqlite3.Error as e:
            logger.error(f"获取结果错误: {str(e)}")
            raise
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
        except sqlite3.Error as e:
            logger.error(f"获取任务结果错误: {str(e)}")
            raise
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
        except sqlite3.Error as e:
            logger.error(f"删除结果错误: {str(e)}")
            conn.rollback()
            raise
        finally:
            self.close()
    
    # 数据库维护操作
    def vacuum_database(self):
        """
        整理数据库，回收删除的空间
        """
        conn = self.connect()
        try:
            conn.execute("VACUUM")
            conn.commit()
            logger.info("数据库整理完成")
            return True
        except sqlite3.Error as e:
            logger.error(f"数据库整理错误: {str(e)}")
            return False
        finally:
            self.close()
    
    def optimize_database(self):
        """
        优化数据库性能
        """
        conn = self.connect()
        try:
            conn.execute("PRAGMA optimize")
            conn.commit()
            logger.info("数据库优化完成")
            return True
        except sqlite3.Error as e:
            logger.error(f"数据库优化错误: {str(e)}")
            return False
        finally:
            self.close()
    
    def clear_cache(self):
        """
        清理数据库缓存文件
        """
        try:
            # 关闭所有连接
            self.close()
            
            # 获取WAL和SHM文件路径
            db_path = Path(self.db_path)
            wal_file = db_path.with_suffix(db_path.suffix + "-wal")
            shm_file = db_path.with_suffix(db_path.suffix + "-shm")
            
            # 删除WAL和SHM文件
            if wal_file.exists():
                wal_file.unlink()
                logger.info(f"已删除WAL文件: {wal_file}")
            
            if shm_file.exists():
                shm_file.unlink()
                logger.info(f"已删除SHM文件: {shm_file}")
            
            logger.info("数据库缓存清理完成")
            return True
        except Exception as e:
            logger.error(f"清理数据库缓存错误: {str(e)}")
            return False
    
    def reset_database(self):
        """
        重置数据库（删除并重新创建）
        警告：此操作将删除所有数据！
        """
        try:
            # 关闭所有连接
            self.close()
            
            # 获取数据库文件路径
            db_path = Path(self.db_path)
            wal_file = db_path.with_suffix(db_path.suffix + "-wal")
            shm_file = db_path.with_suffix(db_path.suffix + "-shm")
            
            # 删除数据库文件
            if db_path.exists():
                db_path.unlink()
                logger.info(f"已删除数据库文件: {db_path}")
            
            # 删除WAL和SHM文件
            if wal_file.exists():
                wal_file.unlink()
                logger.info(f"已删除WAL文件: {wal_file}")
            
            if shm_file.exists():
                shm_file.unlink()
                logger.info(f"已删除SHM文件: {shm_file}")
            
            # 重新初始化数据库
            self.initialize_db()
            logger.info("数据库已重置")
            return True
        except Exception as e:
            logger.error(f"重置数据库错误: {str(e)}")
            return False
    
    def backup_database(self, backup_path=None):
        """
        备份数据库
        
        参数:
            backup_path (str, optional): 备份文件路径，默认为数据库路径加上时间戳
        
        返回:
            str: 备份文件路径
        """
        try:
            # 关闭所有连接
            self.close()
            
            # 设置默认备份路径
            if backup_path is None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                db_path = Path(self.db_path)
                backup_path = str(db_path.with_name(f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"))
            
            # 复制数据库文件
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"数据库已备份到: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"备份数据库错误: {str(e)}")
            return None
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
