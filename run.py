#!/usr/bin/env python3
"""
聊天记录分析器启动脚本
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import config
from app import main

def setup_logging():
    """设置日志"""
    log_file = os.path.join(config.LOGS_DIR, 'chatlog_analyzer.log')
    
    # 创建日志处理器
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
    
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper()),
        format=config.LOG_FORMAT,
        handlers=handlers
    )
    
    # 设置第三方库日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('transformers').setLevel(logging.WARNING)
    logging.getLogger('torch').setLevel(logging.WARNING)

def check_dependencies():
    """检查依赖"""
    required_packages = [
        'flask',
        'flask_socketio', 
        'redis',
        'transformers',
        'torch'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        sys.exit(1)
    
    print("✅ 依赖检查通过")

def check_redis_connection():
    """检查Redis连接"""
    try:
        import redis
        client = redis.from_url(config.REDIS_URL)
        client.ping()
        print("✅ Redis连接正常")
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        print(f"请确保Redis服务正在运行，连接地址: {config.REDIS_URL}")
        sys.exit(1)

def check_chatlog_api():
    """检查聊天记录API"""
    try:
        import requests
        response = requests.get(f"{config.CHATLOG_API_URL}/api/v1/session", timeout=5)
        if response.status_code == 200:
            print("✅ 聊天记录API连接正常")
        else:
            print(f"⚠️ 聊天记录API响应异常: {response.status_code}")
    except Exception as e:
        print(f"⚠️ 聊天记录API连接失败: {e}")
        print(f"请确保聊天记录API服务正在运行，地址: {config.CHATLOG_API_URL}")
        print("注意：这不会阻止服务启动，但可能影响数据获取")

def print_startup_info():
    """打印启动信息"""
    print("=" * 60)
    print("🚀 聊天记录分析器")
    print("=" * 60)
    print(f"📍 服务地址: http://{config.HOST}:{config.PORT}")
    print(f"🔧 调试模式: {'开启' if config.DEBUG else '关闭'}")
    print(f"📊 Redis地址: {config.REDIS_URL}")
    print(f"💬 聊天API: {config.CHATLOG_API_URL}")
    print(f"📁 模型目录: {config.MODEL_CACHE_DIR}")
    print(f"📈 图表目录: {config.CHARTS_OUTPUT_DIR}")
    print(f"📝 日志目录: {config.LOGS_DIR}")
    print("=" * 60)
    print("🔗 API文档:")
    print(f"  Swagger UI: http://{config.HOST}:{config.PORT}/docs")
    print(f"  OpenAPI JSON: POST http://{config.HOST}:{config.PORT}/api/v1/swagger.json")
    print("=" * 60)

if __name__ == '__main__':
    try:
        # 设置日志
        setup_logging()
        
        # 打印启动信息
        print_startup_info()
        
        # 检查依赖
        print("🔍 检查系统依赖...")
        check_dependencies()
        
        # 检查Redis连接
        print("🔍 检查Redis连接...")
        check_redis_connection()
        
        # 检查聊天记录API
        print("🔍 检查聊天记录API...")
        check_chatlog_api()
        
        print("\n🎯 启动服务...")
        
        # 启动应用
        main()
        
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)
