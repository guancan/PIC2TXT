"""
配置文件
集中管理应用配置
"""

import os

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOWNLOAD_DIR = os.path.join(DATA_DIR, "downloads")
RESULT_DIR = os.path.join(DATA_DIR, "results")
DB_PATH = os.path.join(BASE_DIR, "database.db")

# 确保目录存在
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# OCR引擎配置
DEFAULT_OCR_ENGINE = "local"  # 默认使用本地引擎

# API配置
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
