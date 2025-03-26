"""
数据库模块
提供数据库连接和操作功能
"""

from database.db_manager import DatabaseManager
from database.models import (
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    CREATE_DATA_SOURCES_TABLE,
    CREATE_NOTE_TASK_RELATIONS_TABLE
)

__all__ = [
    'DatabaseManager',
    'TASK_STATUS_PENDING',
    'TASK_STATUS_PROCESSING',
    'TASK_STATUS_COMPLETED',
    'TASK_STATUS_FAILED'
]
