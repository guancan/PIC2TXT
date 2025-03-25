"""
服务模块
提供下载和OCR处理功能
"""

from services.download_service import Downloader as DownloadService
from services.ocr_factory import OCRFactory

__all__ = ['DownloadService', 'OCRFactory']

# 服务模块包
