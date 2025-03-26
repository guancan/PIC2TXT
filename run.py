#!/usr/bin/env python
"""
启动脚本
用于启动 pics_2_txt 应用
"""

import os
import subprocess
import sys
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 核心依赖项列表
CORE_DEPENDENCIES = [
    "streamlit",
    "requests",
    "pandas",
    "paddleocr",
    "mistralai",
    "python-dotenv"
]

def check_dependencies():
    """检查依赖项是否已安装"""
    missing_deps = []
    for dep in CORE_DEPENDENCIES:
        try:
            __import__(dep.split("==")[0])
        except ImportError:
            missing_deps.append(dep)
    
    if not missing_deps:
        logger.info("✅ 所有核心依赖项已安装")
        return True
    else:
        logger.warning(f"❌ 缺少以下依赖项: {', '.join(missing_deps)}")
        return False

def install_dependencies():
    """安装所需的依赖项"""
    logger.info("正在安装依赖项...")
    try:
        # 优先使用 requirements.txt 安装所有依赖
        if os.path.exists("requirements.txt"):
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            logger.info("✅ 已从 requirements.txt 安装所有依赖项")
        else:
            # 如果没有 requirements.txt，则安装核心依赖
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + CORE_DEPENDENCIES)
            logger.info("✅ 已安装核心依赖项")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ 依赖项安装失败: {e}")
        return False

def create_directories():
    """创建必要的目录"""
    os.makedirs("data/downloads", exist_ok=True)
    os.makedirs("data/results", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    logger.info("✅ 已创建必要的目录")

def check_env_file():
    """检查 .env 文件是否存在"""
    if not os.path.exists(".env"):
        logger.warning("⚠️ 未找到 .env 文件，将使用默认配置")
        # 创建一个空的 .env 文件
        with open(".env", "w") as f:
            f.write("# Mistral AI API 密钥\n")
            f.write("MISTRAL_API_KEY=\n")
        logger.info("✅ 已创建空的 .env 文件，请在其中设置 MISTRAL_API_KEY")

def run_app():
    """运行Streamlit应用"""
    logger.info("正在启动应用...")
    subprocess.run(["streamlit", "run", "app.py"])

if __name__ == "__main__":
    print("=" * 50)
    print("pics_2_txt 启动程序")
    print("=" * 50)
    
    # 检查依赖项
    if not check_dependencies():
        if not install_dependencies():
            logger.error("无法安装依赖项，请手动安装后重试")
            sys.exit(1)
    
    # 创建目录
    create_directories()
    
    # 检查 .env 文件
    check_env_file()
    
    # 运行应用
    run_app() 