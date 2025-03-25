"""
数据库管理类
负责数据库连接和基本的CRUD操作
"""

import sqlite3
import os
import datetime
import logging
import shutil
import time
from pathlib import Path
from database.models import (
    CREATE_TASKS_TABLE, 
    CREATE_RESULTS_TABLE,
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED
)
from config import DB_PATH

# 设置日志
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path=None):
        """初始化数据库管理器"""
        # 如果未提供路径，使用配置中的默认路径
        self.db_path = db_path or DB_PATH
        self.conn = None
        self.cursor = None
        self.initialize_db()
    
    def connect(self):
        """连接到数据库"""
        try:
            # 如果已经有连接，先关闭
            if self.conn:
                self.close()
                
            # 确保数据库目录存在
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                
            # 连接数据库
            self.conn = sqlite3.connect(self.db_path, timeout=20)
            
            # 启用外键约束
            self.conn.execute("PRAGMA foreign_keys = ON")
            # 设置超时时间
            self.conn.execute("PRAGMA busy_timeout = 10000")
            # 设置同步模式为NORMAL (1)，提高性能
            self.conn.execute("PRAGMA synchronous = 1")
            # 设置日志模式为WAL，提高性能和可靠性
            self.conn.execute("PRAGMA journal_mode = WAL")
            # 设置缓存大小
            self.conn.execute("PRAGMA cache_size = 10000")
            
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
            task_id = cursor.lastrowid
            logger.info(f"成功创建任务 ID: {task_id}")
            return task_id  # 返回新创建任务的ID
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
            if task:
                logger.debug(f"获取到任务 ID: {task_id}")
                return dict(task)
            else:
                logger.warning(f"未找到任务 ID: {task_id}")
                return None
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
            task_list = [dict(task) for task in tasks]
            logger.info(f"获取到 {len(task_list)} 个任务")
            return task_list
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
            task_list = [dict(task) for task in tasks]
            logger.info(f"获取到 {len(task_list)} 个待处理任务")
            return task_list
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
            success = cursor.rowcount > 0
            if success:
                logger.info(f"成功更新任务状态 ID: {task_id}, 状态: {status}")
            else:
                logger.warning(f"更新任务状态失败 ID: {task_id}, 状态: {status}")
            return success
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
            success = cursor.rowcount > 0
            if success:
                logger.info(f"成功更新任务文件路径 ID: {task_id}, 路径: {file_path}")
            else:
                logger.warning(f"更新任务文件路径失败 ID: {task_id}, 路径: {file_path}")
            return success
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
            return False
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
            result_id = cursor.lastrowid
            
            # 更新任务状态为已完成
            self.update_task_status(task_id, TASK_STATUS_COMPLETED)
            
            logger.info(f"成功创建结果 ID: {result_id}, 任务ID: {task_id}")
            return result_id  # 返回新创建结果的ID
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
            if result:
                logger.debug(f"获取到结果 ID: {result_id}")
                return dict(result)
            else:
                logger.warning(f"未找到结果 ID: {result_id}")
                return None
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
            result_list = [dict(result) for result in results]
            logger.info(f"获取到任务 {task_id} 的 {len(result_list)} 个结果")
            return result_list
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
            success = cursor.rowcount > 0
            if success:
                logger.info(f"成功删除结果 ID: {result_id}")
            else:
                logger.warning(f"删除结果失败 ID: {result_id}")
            return success
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
            
            # 先执行checkpoint以确保WAL文件中的数据被写入主数据库文件
            temp_conn = sqlite3.connect(self.db_path)
            temp_conn.execute("PRAGMA wal_checkpoint(FULL)")
            temp_conn.close()
            
            # 等待一小段时间确保文件操作完成
            time.sleep(0.5)
            
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
            
            # 等待一小段时间确保文件操作完成
            time.sleep(0.5)
            
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
            
            # 先执行checkpoint以确保WAL文件中的数据被写入主数据库文件
            temp_conn = sqlite3.connect(self.db_path)
            temp_conn.execute("PRAGMA wal_checkpoint(FULL)")
            temp_conn.close()
            
            # 等待一小段时间确保文件操作完成
            time.sleep(0.5)
            
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
    
    def check_database_status(self):
        """
        检查数据库状态
        
        Returns:
            dict: 数据库状态信息
        """
        try:
            self.connect()
            
            # 检查任务表
            self.cursor.execute("SELECT COUNT(*) FROM tasks")
            task_count = self.cursor.fetchone()[0]
            
            # 检查结果表
            self.cursor.execute("SELECT COUNT(*) FROM results")
            result_count = self.cursor.fetchone()[0]
            
            # 获取最近的任务
            self.cursor.execute(
                "SELECT id, status, created_at FROM tasks ORDER BY created_at DESC LIMIT 5"
            )
            recent_tasks = self.cursor.fetchall()
            
            # 检查WAL文件
            db_path = Path(self.db_path)
            wal_file = db_path.with_suffix(db_path.suffix + "-wal")
            shm_file = db_path.with_suffix(db_path.suffix + "-shm")
            
            wal_exists = wal_file.exists()
            wal_size = wal_file.stat().st_size if wal_exists else 0
            
            # 返回状态信息
            return {
                "database_path": self.db_path,
                "database_exists": os.path.exists(self.db_path),
                "database_size": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
                "task_count": task_count,
                "result_count": result_count,
                "recent_tasks": recent_tasks,
                "wal_exists": wal_exists,
                "wal_size": wal_size,
                "status": "正常"
            }
        except Exception as e:
            logger.error(f"数据库状态检查失败: {str(e)}")
            return {
                "database_path": self.db_path,
                "database_exists": os.path.exists(self.db_path),
                "status": f"错误: {str(e)}"
            }
        finally:
            self.close()
    
    def fix_database(self):
        """
        修复数据库文件
        
        Returns:
            bool: 修复是否成功
        """
        try:
            # 关闭所有连接
            self.close()
            
            # 检查是否存在多个数据库文件
            db_files = []
            if os.path.exists(DB_PATH):
                db_files.append(DB_PATH)
            
            default_db = "db.sqlite"
            if os.path.exists(default_db) and default_db != DB_PATH:
                db_files.append(default_db)
            
            if len(db_files) > 1:
                logger.warning(f"发现多个数据库文件: {db_files}")
                
                # 检查哪个数据库有更多数据
                main_db = None
                max_size = 0
                
                for db_file in db_files:
                    size = os.path.getsize(db_file)
                    if size > max_size:
                        max_size = size
                        main_db = db_file
                
                logger.info(f"选择 {main_db} 作为主数据库文件")
                
                # 如果主数据库不是配置中的数据库，则复制它
                if main_db != DB_PATH:
                    # 备份当前配置的数据库（如果存在）
                    if os.path.exists(DB_PATH):
                        backup_path = f"{DB_PATH}.bak"
                        shutil.copy2(DB_PATH, backup_path)
                        logger.info(f"已备份当前数据库到 {backup_path}")
                    
                    # 复制主数据库到配置的位置
                    shutil.copy2(main_db, DB_PATH)
                    logger.info(f"已复制 {main_db} 到 {DB_PATH}")
                    
                    # 删除WAL文件
                    for db_file in db_files:
                        wal_file = f"{db_file}-wal"
                        shm_file = f"{db_file}-shm"
                        
                        if os.path.exists(wal_file):
                            os.remove(wal_file)
                            logger.info(f"已删除 {wal_file}")
                        
                        if os.path.exists(shm_file):
                            os.remove(shm_file)
                            logger.info(f"已删除 {shm_file}")
            
            # 重新连接数据库并执行VACUUM
            self.connect()
            self.conn.execute("VACUUM")
            self.conn.commit()
            
            # 执行完整的WAL检查点
            self.conn.execute("PRAGMA wal_checkpoint(FULL)")
            self.conn.commit()
            
            logger.info("数据库修复完成")
            return True
        except Exception as e:
            logger.error(f"修复数据库失败: {str(e)}")
            return False
        finally:
            self.close()
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
