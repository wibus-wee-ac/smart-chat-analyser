"""
配置文件
集中管理所有配置项
"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """应用配置"""
    
    # 基础配置
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', '6142'))
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'chatlog-analyzer-secret-key')
    
    # Redis配置
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # 聊天记录API配置
    CHATLOG_API_URL: str = os.getenv('CHATLOG_API_URL', 'http://127.0.0.1:5030')
    
    # 任务队列配置
    TASK_QUEUE_MAX_WORKERS: int = int(os.getenv('TASK_QUEUE_MAX_WORKERS', '4'))
    TASK_RESULT_TTL: int = int(os.getenv('TASK_RESULT_TTL', '86400'))  # 24小时
    
    # 分析服务配置
    ANALYSIS_MAX_WORKERS: int = int(os.getenv('ANALYSIS_MAX_WORKERS', '4'))
    PREPROCESSING_MAX_WORKERS: int = int(os.getenv('PREPROCESSING_MAX_WORKERS', '4'))
    
    # 模型配置
    MODEL_CACHE_DIR: str = os.getenv('MODEL_CACHE_DIR', './models')
    SENTIMENT_MODEL: str = os.getenv('SENTIMENT_MODEL', 'uer/roberta-base-finetuned-chinanews-chinese')
    AUTO_PRELOAD_MODELS: bool = os.getenv('AUTO_PRELOAD_MODELS', 'False').lower() == 'true'
    
    # 文件存储配置
    CHARTS_OUTPUT_DIR: str = os.getenv('CHARTS_OUTPUT_DIR', './charts')
    LOGS_DIR: str = os.getenv('LOGS_DIR', './logs')
    
    # 日志配置
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT: str = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 性能配置
    MAX_CONTENT_LENGTH: int = int(os.getenv('MAX_CONTENT_LENGTH', '16777216'))  # 16MB
    
    def __post_init__(self):
        """配置后处理"""
        # 确保目录存在
        os.makedirs(self.MODEL_CACHE_DIR, exist_ok=True)
        os.makedirs(self.CHARTS_OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)

# 全局配置实例
config = Config()
