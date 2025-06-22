"""
分析器注册表
支持动态加载和管理分析器插件
"""

import logging
import importlib
import inspect
from typing import Dict, Any, Type, List, Optional
from pathlib import Path

from analyzers.base import BaseAnalyzer

logger = logging.getLogger(__name__)

class AnalyzerRegistry:
    """分析器注册表"""
    
    def __init__(self):
        """初始化分析器注册表"""
        self._analyzers: Dict[str, Type[BaseAnalyzer]] = {}
        self._analyzer_instances: Dict[str, BaseAnalyzer] = {}
        self._analyzer_metadata: Dict[str, Dict[str, Any]] = {}
        
        # 自动注册内置分析器
        self._register_builtin_analyzers()
        
        logger.info("分析器注册表初始化完成")
    
    def register_analyzer(self, name: str, analyzer_class: Type[BaseAnalyzer], 
                         metadata: Optional[Dict[str, Any]] = None):
        """
        注册分析器
        
        Args:
            name: 分析器名称
            analyzer_class: 分析器类
            metadata: 分析器元数据
        """
        if not issubclass(analyzer_class, BaseAnalyzer):
            raise ValueError(f"分析器类必须继承自BaseAnalyzer: {analyzer_class}")
        
        if name in self._analyzers:
            logger.warning(f"分析器 {name} 已存在，将被覆盖")
        
        self._analyzers[name] = analyzer_class
        self._analyzer_metadata[name] = metadata or {}
        
        # 清除可能存在的实例缓存
        if name in self._analyzer_instances:
            del self._analyzer_instances[name]
        
        logger.info(f"分析器已注册: {name}")
    
    def unregister_analyzer(self, name: str):
        """注销分析器"""
        if name not in self._analyzers:
            logger.warning(f"分析器 {name} 不存在")
            return
        
        del self._analyzers[name]
        
        if name in self._analyzer_instances:
            del self._analyzer_instances[name]
        
        if name in self._analyzer_metadata:
            del self._analyzer_metadata[name]
        
        logger.info(f"分析器已注销: {name}")
    
    def get_analyzer(self, name: str, **kwargs) -> BaseAnalyzer:
        """
        获取分析器实例
        
        Args:
            name: 分析器名称
            **kwargs: 分析器初始化参数
            
        Returns:
            分析器实例
        """
        if name not in self._analyzers:
            raise ValueError(f"未知的分析器: {name}")
        
        # 检查是否有缓存的实例
        cache_key = f"{name}_{hash(frozenset(kwargs.items()))}"
        
        if cache_key not in self._analyzer_instances:
            analyzer_class = self._analyzers[name]
            self._analyzer_instances[cache_key] = analyzer_class(**kwargs)
        
        return self._analyzer_instances[cache_key]
    
    def create_analyzer(self, name: str, **kwargs) -> BaseAnalyzer:
        """
        创建新的分析器实例（不使用缓存）
        
        Args:
            name: 分析器名称
            **kwargs: 分析器初始化参数
            
        Returns:
            新的分析器实例
        """
        if name not in self._analyzers:
            raise ValueError(f"未知的分析器: {name}")
        
        analyzer_class = self._analyzers[name]
        return analyzer_class(**kwargs)
    
    def get_available_analyzers(self) -> List[str]:
        """获取可用的分析器列表"""
        return list(self._analyzers.keys())
    
    def get_analyzer_info(self, name: str) -> Dict[str, Any]:
        """获取分析器信息"""
        if name not in self._analyzers:
            raise ValueError(f"未知的分析器: {name}")
        
        analyzer_class = self._analyzers[name]
        metadata = self._analyzer_metadata.get(name, {})
        
        # 获取类信息
        class_info = {
            'class_name': analyzer_class.__name__,
            'module': analyzer_class.__module__,
            'doc': analyzer_class.__doc__,
        }
        
        # 获取初始化参数
        init_signature = inspect.signature(analyzer_class.__init__)
        init_params = {}
        for param_name, param in init_signature.parameters.items():
            if param_name != 'self':
                init_params[param_name] = {
                    'type': str(param.annotation) if param.annotation != param.empty else 'Any',
                    'default': param.default if param.default != param.empty else None,
                    'required': param.default == param.empty
                }
        
        return {
            'name': name,
            'class_info': class_info,
            'init_params': init_params,
            'metadata': metadata,
            'is_registered': True
        }
    
    def load_analyzer_from_file(self, file_path: str, analyzer_name: Optional[str] = None):
        """
        从文件加载分析器
        
        Args:
            file_path: 分析器文件路径
            analyzer_name: 分析器名称（如果不提供，使用文件名）
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"分析器文件不存在: {file_path}")
            
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找BaseAnalyzer的子类
            analyzer_classes = []
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseAnalyzer) and obj != BaseAnalyzer:
                    analyzer_classes.append((name, obj))
            
            if not analyzer_classes:
                raise ValueError(f"文件中未找到BaseAnalyzer的子类: {file_path}")
            
            # 如果有多个类，选择第一个或指定的类
            if len(analyzer_classes) == 1:
                class_name, analyzer_class = analyzer_classes[0]
            else:
                if analyzer_name:
                    analyzer_class = None
                    for name, cls in analyzer_classes:
                        if name == analyzer_name:
                            analyzer_class = cls
                            break
                    if not analyzer_class:
                        raise ValueError(f"未找到指定的分析器类: {analyzer_name}")
                else:
                    class_name, analyzer_class = analyzer_classes[0]
                    logger.warning(f"文件中有多个分析器类，使用第一个: {class_name}")
            
            # 注册分析器
            register_name = analyzer_name or file_path.stem
            metadata = {
                'source': 'file',
                'file_path': str(file_path),
                'class_name': analyzer_class.__name__,
                'loaded_at': logger.info(f"从文件加载分析器: {register_name}")
            }
            
            self.register_analyzer(register_name, analyzer_class, metadata)
            
            logger.info(f"从文件加载分析器成功: {register_name}")
            
        except Exception as e:
            logger.error(f"从文件加载分析器失败: {e}")
            raise
    
    def load_analyzers_from_directory(self, directory_path: str):
        """
        从目录加载所有分析器
        
        Args:
            directory_path: 分析器目录路径
        """
        try:
            directory = Path(directory_path)
            
            if not directory.exists():
                raise FileNotFoundError(f"分析器目录不存在: {directory}")
            
            # 查找所有Python文件
            python_files = list(directory.glob("*.py"))
            
            loaded_count = 0
            for file_path in python_files:
                if file_path.name.startswith('__'):
                    continue
                
                try:
                    self.load_analyzer_from_file(str(file_path))
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"加载分析器文件失败 {file_path}: {e}")
            
            logger.info(f"从目录加载了 {loaded_count} 个分析器: {directory}")
            
        except Exception as e:
            logger.error(f"从目录加载分析器失败: {e}")
            raise
    
    def _register_builtin_analyzers(self):
        """注册内置分析器"""
        try:
            from analyzers import (
                WordFrequencyAnalyzer,
                TimePatternAnalyzer,
                SentimentAnalyzer,
                SocialNetworkAnalyzer
            )
            
            builtin_analyzers = {
                'word_frequency': (WordFrequencyAnalyzer, {
                    'category': 'text_analysis',
                    'description': '高频词汇分析',
                    'builtin': True
                }),
                'time_pattern': (TimePatternAnalyzer, {
                    'category': 'temporal_analysis',
                    'description': '时间模式分析',
                    'builtin': True
                }),
                'sentiment': (SentimentAnalyzer, {
                    'category': 'text_analysis',
                    'description': '情感分析',
                    'builtin': True
                }),
                'social_network': (SocialNetworkAnalyzer, {
                    'category': 'network_analysis',
                    'description': '社交网络分析',
                    'builtin': True
                })
            }
            
            for name, (analyzer_class, metadata) in builtin_analyzers.items():
                self.register_analyzer(name, analyzer_class, metadata)
            
            logger.info(f"注册了 {len(builtin_analyzers)} 个内置分析器")
            
        except Exception as e:
            logger.error(f"注册内置分析器失败: {e}")
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        builtin_count = sum(1 for metadata in self._analyzer_metadata.values() 
                           if metadata.get('builtin', False))
        
        categories = {}
        for metadata in self._analyzer_metadata.values():
            category = metadata.get('category', 'unknown')
            categories[category] = categories.get(category, 0) + 1
        
        return {
            'total_analyzers': len(self._analyzers),
            'builtin_analyzers': builtin_count,
            'custom_analyzers': len(self._analyzers) - builtin_count,
            'cached_instances': len(self._analyzer_instances),
            'categories': categories
        }


# 装饰器用于注册分析器
def register_analyzer(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    分析器注册装饰器
    
    Args:
        name: 分析器名称
        metadata: 分析器元数据
    """
    def decorator(analyzer_class: Type[BaseAnalyzer]):
        registry.register_analyzer(name, analyzer_class, metadata)
        return analyzer_class
    
    return decorator


# 全局分析器注册表实例
registry = AnalyzerRegistry()


def get_analyzer_registry() -> AnalyzerRegistry:
    """获取分析器注册表实例"""
    return registry
