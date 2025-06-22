"""
模型管理器
单例模式管理所有AI模型，避免重复加载
支持预加载功能，提升用户体验
"""

import logging
import threading
import asyncio
import time
from typing import Dict, Any, Optional, List, Callable
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import torch
import gc

logger = logging.getLogger(__name__)

class PreloadStatus(Enum):
    """预加载状态枚举"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ModelManager:
    """模型管理器 - 单例模式，支持预加载功能"""

    _instance = None
    _lock = threading.Lock()
    _models = {}
    _model_locks = {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._models = {}
        self._model_locks = {}

        # 预加载相关属性
        self._preload_status = {}
        self._preload_progress = {}
        self._preload_errors = {}
        self._preload_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ModelPreload")
        self._preload_futures = {}

        # 可用的模型列表
        self._available_models = {
            "sentiment_model": {
                "name": "情感分析模型",
                "loader": self._load_sentiment_model,
                "priority": 1  # 优先级，数字越小优先级越高
            },
            "bertopic_model": {
                "name": "BERTopic主题模型",
                "loader": self._load_bertopic_model,
                "priority": 2
            }
        }

        # 初始化预加载状态
        for model_key in self._available_models:
            self._preload_status[model_key] = PreloadStatus.NOT_STARTED
            self._preload_progress[model_key] = 0.0
            self._preload_errors[model_key] = None

        logger.info("模型管理器初始化完成，支持预加载功能")
    
    def get_sentiment_model(self) -> Any:
        """获取情感分析模型"""
        model_key = "sentiment_model"
        
        if model_key not in self._models:
            with self._get_model_lock(model_key):
                if model_key not in self._models:
                    logger.info("正在加载情感分析模型...")
                    self._models[model_key] = self._load_sentiment_model()
                    logger.info("情感分析模型加载完成")
        
        return self._models[model_key]
    
    def get_bertopic_model(self) -> Any:
        """获取BERTopic模型"""
        model_key = "bertopic_model"
        
        if model_key not in self._models:
            with self._get_model_lock(model_key):
                if model_key not in self._models:
                    logger.info("正在加载BERTopic模型...")
                    self._models[model_key] = self._load_bertopic_model()
                    logger.info("BERTopic模型加载完成")
        
        return self._models[model_key]
    
    def _get_model_lock(self, model_key: str) -> threading.Lock:
        """获取模型专用锁"""
        if model_key not in self._model_locks:
            self._model_locks[model_key] = threading.Lock()
        return self._model_locks[model_key]
    
    def _load_sentiment_model(self) -> Any:
        """加载情感分析模型"""
        try:
            from transformers import pipeline

            # 使用正确的中文情感分析模型
            model_name = "IDEA-CCNL/Erlangshen-Roberta-110M-Sentiment"

            # 检查设备
            device = -1  # CPU
            if torch.cuda.is_available():
                device = 0
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = 0  # MPS for Apple Silicon

            pipeline_model = pipeline(
                "sentiment-analysis",
                model=model_name,
                device=device,
                torch_dtype=torch.float16 if device >= 0 else torch.float32,
                model_kwargs={"low_cpu_mem_usage": True}
            )

            return pipeline_model

        except Exception as e:
            logger.error(f"加载情感分析模型失败: {e}")
            return None
    
    def _load_bertopic_model(self) -> Any:
        """加载BERTopic模型"""
        try:
            from bertopic import BERTopic
            from sentence_transformers import SentenceTransformer
            
            # 使用中文优化的sentence transformer
            embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            
            # 创建BERTopic模型
            topic_model = BERTopic(
                embedding_model=embedding_model,
                language="chinese",
                calculate_probabilities=True,
                verbose=True
            )
            
            return topic_model
            
        except Exception as e:
            logger.error(f"加载BERTopic模型失败: {e}")
            return None
    
    def preload_model(self, model_key: str, force: bool = False) -> bool:
        """
        预加载指定模型

        Args:
            model_key: 模型键名
            force: 是否强制重新加载已加载的模型

        Returns:
            bool: 是否成功启动预加载
        """
        if model_key not in self._available_models:
            logger.error(f"未知的模型: {model_key}")
            return False

        # 如果模型已加载且不强制重新加载，直接返回
        if model_key in self._models and not force:
            logger.info(f"模型 {model_key} 已加载，跳过预加载")
            self._preload_status[model_key] = PreloadStatus.COMPLETED
            self._preload_progress[model_key] = 100.0
            return True

        # 如果正在预加载中，返回当前状态
        if self._preload_status[model_key] == PreloadStatus.IN_PROGRESS:
            logger.info(f"模型 {model_key} 正在预加载中")
            return True

        # 开始预加载
        self._preload_status[model_key] = PreloadStatus.IN_PROGRESS
        self._preload_progress[model_key] = 0.0
        self._preload_errors[model_key] = None

        # 提交预加载任务
        future = self._preload_executor.submit(self._preload_model_worker, model_key)
        self._preload_futures[model_key] = future

        logger.info(f"开始预加载模型: {model_key}")
        return True

    def preload_all_models(self, force: bool = False) -> Dict[str, bool]:
        """
        预加载所有模型

        Args:
            force: 是否强制重新加载已加载的模型

        Returns:
            Dict[str, bool]: 每个模型的预加载启动状态
        """
        results = {}

        # 按优先级排序
        sorted_models = sorted(
            self._available_models.items(),
            key=lambda x: x[1]["priority"]
        )

        for model_key, _ in sorted_models:
            results[model_key] = self.preload_model(model_key, force)

        logger.info(f"批量预加载启动完成: {results}")
        return results

    def _preload_model_worker(self, model_key: str):
        """预加载工作线程"""
        try:
            model_info = self._available_models[model_key]
            loader_func = model_info["loader"]

            logger.info(f"开始加载模型: {model_info['name']}")
            self._preload_progress[model_key] = 10.0

            # 加载模型
            model = loader_func()
            self._preload_progress[model_key] = 90.0

            if model is not None:
                # 使用模型锁确保线程安全
                with self._get_model_lock(model_key):
                    self._models[model_key] = model

                self._preload_status[model_key] = PreloadStatus.COMPLETED
                self._preload_progress[model_key] = 100.0
                logger.info(f"模型预加载完成: {model_info['name']}")
            else:
                raise Exception("模型加载返回None")

        except Exception as e:
            self._preload_status[model_key] = PreloadStatus.FAILED
            self._preload_errors[model_key] = str(e)
            logger.error(f"模型预加载失败 {model_key}: {e}")
        finally:
            # 清理future引用
            if model_key in self._preload_futures:
                del self._preload_futures[model_key]

    def get_preload_status(self, model_key: str = None) -> Dict[str, Any]:
        """
        获取预加载状态

        Args:
            model_key: 指定模型键名，为None时返回所有模型状态

        Returns:
            Dict: 预加载状态信息
        """
        if model_key:
            if model_key not in self._available_models:
                return {"error": f"未知的模型: {model_key}"}

            return {
                "model_key": model_key,
                "model_name": self._available_models[model_key]["name"],
                "status": self._preload_status[model_key].value,
                "progress": self._preload_progress[model_key],
                "error": self._preload_errors[model_key],
                "is_loaded": model_key in self._models
            }
        else:
            # 返回所有模型状态
            status_info = {}
            for key in self._available_models:
                status_info[key] = {
                    "model_name": self._available_models[key]["name"],
                    "status": self._preload_status[key].value,
                    "progress": self._preload_progress[key],
                    "error": self._preload_errors[key],
                    "is_loaded": key in self._models,
                    "priority": self._available_models[key]["priority"]
                }
            return status_info

    def cancel_preload(self, model_key: str) -> bool:
        """
        取消预加载任务

        Args:
            model_key: 模型键名

        Returns:
            bool: 是否成功取消
        """
        if model_key not in self._available_models:
            return False

        if model_key in self._preload_futures:
            future = self._preload_futures[model_key]
            if not future.done():
                cancelled = future.cancel()
                if cancelled:
                    self._preload_status[model_key] = PreloadStatus.NOT_STARTED
                    self._preload_progress[model_key] = 0.0
                    self._preload_errors[model_key] = None
                    logger.info(f"已取消模型预加载: {model_key}")
                return cancelled

        return False

    def get_model_info(self) -> Dict[str, Any]:
        """获取已加载模型信息"""
        info = {
            "loaded_models": list(self._models.keys()),
            "model_count": len(self._models),
            "memory_usage": self._get_memory_usage(),
            "available_models": list(self._available_models.keys()),
            "preload_status": self.get_preload_status()
        }
        return info
    
    def _get_memory_usage(self) -> Dict[str, str]:
        """获取内存使用情况"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss": f"{memory_info.rss / 1024 / 1024:.2f} MB",
                "vms": f"{memory_info.vms / 1024 / 1024:.2f} MB"
            }
        except ImportError:
            return {"error": "psutil not installed"}
    
    def clear_model(self, model_key: str):
        """清除指定模型"""
        if model_key in self._models:
            del self._models[model_key]

            # 重置预加载状态
            if model_key in self._preload_status:
                self._preload_status[model_key] = PreloadStatus.NOT_STARTED
                self._preload_progress[model_key] = 0.0
                self._preload_errors[model_key] = None

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info(f"已清除模型: {model_key}")

    def clear_all_models(self):
        """清除所有模型"""
        # 取消所有正在进行的预加载任务
        for model_key in list(self._preload_futures.keys()):
            self.cancel_preload(model_key)

        self._models.clear()

        # 重置所有预加载状态
        for model_key in self._available_models:
            self._preload_status[model_key] = PreloadStatus.NOT_STARTED
            self._preload_progress[model_key] = 0.0
            self._preload_errors[model_key] = None

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("已清除所有模型")

    def shutdown(self):
        """关闭模型管理器，清理资源"""
        logger.info("正在关闭模型管理器...")

        # 取消所有预加载任务
        for model_key in list(self._preload_futures.keys()):
            self.cancel_preload(model_key)

        # 关闭线程池
        self._preload_executor.shutdown(wait=True)

        # 清除所有模型
        self.clear_all_models()

        logger.info("模型管理器已关闭")


# 全局模型管理器实例
model_manager = ModelManager()


def get_model_manager() -> ModelManager:
    """获取模型管理器实例"""
    return model_manager
