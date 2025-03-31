"""
配置文件
包含应用程序的全局配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv  # 导入dotenv库

# 加载.env文件中的环境变量
load_dotenv()  # 这会自动查找项目根目录下的.env文件并加载其中的变量

# 基础路径配置
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = os.path.join(BASE_DIR, "temp")
RESULT_DIR = os.path.join(BASE_DIR, "data/results")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "data/downloads")

# 数据库配置
DB_PATH = os.path.join(BASE_DIR, "database.db")  # 添加数据库路径配置

# 确保必要的目录存在
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# OCR引擎配置
DEFAULT_OCR_ENGINE = "mistral"  # 默认OCR引擎

# Mistral AI API配置
# 从环境变量中获取API密钥
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")

# 阿里云Paraformer API配置
ALI_PARAFORMER_API_KEY = os.environ.get("ALI_PARAFORMER_API_KEY", "")

# 其他OCR服务配置
# ...

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
