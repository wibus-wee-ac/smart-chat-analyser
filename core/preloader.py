"""
预加载管理器
统一管理模型和用户缓存的预加载
"""

import logging
import threading
import time
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config
from core.user_cache import init_user_cache, get_user_cache
from utils.message_parser import init_message_parser_with_cache

logger = logging.getLogger(__name__)


class PreloadManager:
    """预加载管理器"""
    
    def __init__(self):
        self.config = Config()
        self._preload_status = {
            'models': {'status': 'not_started', 'error': None, 'start_time': None, 'end_time': None},
            'user_cache': {'status': 'not_started', 'error': None, 'start_time': None, 'end_time': None}
        }
        self._lock = threading.RLock()
    
    def preload_all(self) -> Dict[str, Any]:
        """
        预加载所有资源
        
        Returns:
            预加载结果
        """
        logger.info("开始预加载所有资源...")
        start_time = time.time()
        
        tasks = []
        
        # 添加用户缓存预加载任务
        if self.config.AUTO_PRELOAD_USER_CACHE:
            tasks.append(('user_cache', self._preload_user_cache))
        
        # 添加模型预加载任务
        if self.config.AUTO_PRELOAD_MODELS:
            tasks.append(('models', self._preload_models))
        
        if not tasks:
            logger.info("没有启用自动预加载")
            return {'success': True, 'message': '没有启用自动预加载', 'results': {}}
        
        # 并行执行预加载任务
        results = {}
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_task = {executor.submit(task_func): task_name for task_name, task_func in tasks}
            
            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    result = future.result()
                    results[task_name] = result
                    logger.info(f"{task_name} 预加载完成: {result}")
                except Exception as e:
                    error_msg = f"{task_name} 预加载失败: {e}"
                    logger.error(error_msg)
                    results[task_name] = {'success': False, 'error': str(e)}
        
        total_time = time.time() - start_time
        logger.info(f"所有资源预加载完成，总耗时: {total_time:.2f}s")
        
        return {
            'success': True,
            'total_time': total_time,
            'results': results
        }
    
    def _preload_user_cache(self) -> Dict[str, Any]:
        """预加载用户缓存"""
        with self._lock:
            self._preload_status['user_cache']['status'] = 'loading'
            self._preload_status['user_cache']['start_time'] = time.time()
        
        try:
            logger.info("开始预加载用户缓存...")
            
            # 初始化用户缓存
            user_cache = init_user_cache()
            
            # 加载缓存数据
            success = user_cache.load_cache()
            
            if success:
                # 将用户缓存集成到消息解析器中
                init_message_parser_with_cache(user_cache)
                
                with self._lock:
                    self._preload_status['user_cache']['status'] = 'completed'
                    self._preload_status['user_cache']['end_time'] = time.time()
                
                stats = user_cache.get_cache_stats()
                return {
                    'success': True,
                    'message': '用户缓存预加载成功',
                    'stats': stats
                }
            else:
                error_msg = user_cache.load_error or '未知错误'
                with self._lock:
                    self._preload_status['user_cache']['status'] = 'failed'
                    self._preload_status['user_cache']['error'] = error_msg
                    self._preload_status['user_cache']['end_time'] = time.time()
                
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"用户缓存预加载异常: {e}"
            logger.error(error_msg)
            
            with self._lock:
                self._preload_status['user_cache']['status'] = 'failed'
                self._preload_status['user_cache']['error'] = error_msg
                self._preload_status['user_cache']['end_time'] = time.time()
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _preload_models(self) -> Dict[str, Any]:
        """预加载模型（保留原有逻辑）"""
        with self._lock:
            self._preload_status['models']['status'] = 'loading'
            self._preload_status['models']['start_time'] = time.time()
        
        try:
            logger.info("开始预加载模型...")
            
            # 这里可以添加实际的模型预加载逻辑
            # 目前只是模拟
            time.sleep(1)  # 模拟加载时间
            
            with self._lock:
                self._preload_status['models']['status'] = 'completed'
                self._preload_status['models']['end_time'] = time.time()
            
            return {
                'success': True,
                'message': '模型预加载成功'
            }
            
        except Exception as e:
            error_msg = f"模型预加载异常: {e}"
            logger.error(error_msg)
            
            with self._lock:
                self._preload_status['models']['status'] = 'failed'
                self._preload_status['models']['error'] = error_msg
                self._preload_status['models']['end_time'] = time.time()
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_preload_status(self) -> Dict[str, Any]:
        """获取预加载状态"""
        with self._lock:
            status = {}
            for resource, info in self._preload_status.items():
                status[resource] = {
                    'status': info['status'],
                    'error': info['error'],
                    'duration': None
                }
                
                if info['start_time'] and info['end_time']:
                    status[resource]['duration'] = info['end_time'] - info['start_time']
                elif info['start_time']:
                    status[resource]['duration'] = time.time() - info['start_time']
            
            return status
    
    def reload_user_cache(self) -> Dict[str, Any]:
        """重新加载用户缓存"""
        logger.info("手动重新加载用户缓存...")
        return self._preload_user_cache()
    
    def get_user_cache_stats(self) -> Dict[str, Any]:
        """获取用户缓存统计信息"""
        user_cache = get_user_cache()
        return user_cache.get_cache_stats()


# 全局预加载管理器实例
_preload_manager: Optional[PreloadManager] = None


def get_preload_manager() -> PreloadManager:
    """获取全局预加载管理器实例"""
    global _preload_manager
    if _preload_manager is None:
        _preload_manager = PreloadManager()
    return _preload_manager


def init_preload_manager() -> PreloadManager:
    """初始化全局预加载管理器"""
    global _preload_manager
    _preload_manager = PreloadManager()
    return _preload_manager
