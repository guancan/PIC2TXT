"""
OCR服务测试脚本
"""

import os
import sys
import logging
import argparse
from services.ocr_factory import OCRFactory
import config
from mistralai import Mistral
import base64
from dotenv import load_dotenv

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ocr(image_path, ocr_engine="local"):
    """测试OCR服务"""
    # 创建OCR服务实例
    ocr_service = OCRFactory.create_ocr_service(service_type=ocr_engine)
    
    # 检查OCR服务是否可用
    if not ocr_service.check_installation():
        logger.error(f"OCR服务 {ocr_engine} 不可用")
        return False
    
    # 处理图片
    result = ocr_service.process_image(image_path)
    
    if result["success"]:
        logger.info(f"OCR识别成功: {result['result_path']}")
        logger.info(f"文本内容: {result['text_content'][:200]}...")  # 只显示前200个字符
        return True
    else:
        logger.error(f"OCR识别失败: {result['error']}")
        return False

def test_document_understanding(image_path):
    """测试使用自然语言询问方式获取图片内容"""
    # 初始化Mistral客户端
    if "MISTRAL_API_KEY" not in os.environ:
        logger.error("未找到MISTRAL_API_KEY环境变量")
        return False
    
    client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    
    # 处理本地图片
    base64_image = encode_image(image_path)
    if not base64_image:
        return False
    
    image_url = f"data:image/jpeg;base64,{base64_image}"
    
    # 使用自然语言询问图片内容
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请以Markdown格式反馈图片内容给我，尽量还原图片中的信息内容和文章结构，如果有插图，则请用语言描述插图内容、放在插图所在段落位置。"
                },
                {
                    "type": "image_url",
                    "image_url": image_url
                }
            ]
        }
    ]
    
    # 获取响应
    chat_response = client.chat.complete(
        model="mistral-small-latest",  # 或使用其他适合的模型
        messages=messages
    )
    
    # 打印并记录结果
    logger.info("文档理解响应内容：")
    print(chat_response.choices[0].message.content)
    
    # 可以添加断言来验证响应是否符合预期
    assert chat_response.choices[0].message.content, "响应内容不应为空"
    return True
    # 可以添加更多断言来验证响应的格式和内容

def encode_image(image_path):
    """将图片编码为base64格式"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"错误：找不到文件 {image_path}")
        return None
    except Exception as e:
        print(f"错误：{e}")
        return None

if __name__ == "__main__":
    # 加载.env文件中的环境变量
    load_dotenv()

    # 使用argparse处理命令行参数，更好地处理特殊字符
    parser = argparse.ArgumentParser(description='测试OCR服务')
    parser.add_argument('image_path', help='图片文件路径')
    parser.add_argument('--engine', default='local', 
                       help='OCR引擎类型 (local 或 mistral)')
    parser.add_argument('--mode', default='ocr', choices=['ocr', 'document'],
                       help='测试模式：ocr(默认)/document(文档理解)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image_path):
        logger.error(f"文件不存在: {args.image_path}")
        sys.exit(1)
    
    # 根据模式选择测试方法
    if args.mode == 'ocr':
        success = test_ocr(args.image_path, args.engine)
    elif args.mode == 'document':
        success = test_document_understanding(args.image_path)
    else:
        logger.error("不支持的测试模式")
        sys.exit(1)
    
    sys.exit(0 if success else 1) 