#!/usr/bin/env python
"""
启动脚本
用于启动 pics_2_txt 应用
"""

import os
import subprocess
import sys

def check_dependencies():
    """检查依赖项是否已安装"""
    try:
        import streamlit
        import requests
        import pandas
        print("✅ 所有依赖项已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖项: {e}")
        return False

def install_dependencies():
    """安装所需的依赖项"""
    print("正在安装依赖项...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit", "requests", "pandas"])
    print("✅ 依赖项安装完成")

def create_directories():
    """创建必要的目录"""
    os.makedirs("data/downloads", exist_ok=True)
    os.makedirs("data/results", exist_ok=True)
    print("✅ 已创建必要的目录")

def run_app():
    """运行Streamlit应用"""
    print("正在启动应用...")
    subprocess.run(["streamlit", "run", "app.py"])

if __name__ == "__main__":
    print("=" * 50)
    print("pics_2_txt 启动程序")
    print("=" * 50)
    
    # 检查依赖项
    if not check_dependencies():
        install_dependencies()
    
    # 创建目录
    create_directories()
    
    # 运行应用
    run_app() 