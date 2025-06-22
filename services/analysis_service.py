"""
分析服务
独立的分析服务，支持并发执行多个分析器
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from core.analyzer_registry import get_analyzer_registry

logger = logging.getLogger(__name__)

class AnalysisService:
    """分析服务"""
    
    def __init__(self, max_workers: int = 4):
        """
        初始化分析服务

        Args:
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 获取分析器注册表
        self.analyzer_registry = get_analyzer_registry()

        logger.info(f"分析服务初始化完成，工作线程数: {max_workers}")

    def get_analyzer(self, analyzer_name: str):
        """获取分析器实例"""
        return self.analyzer_registry.get_analyzer(analyzer_name)
    
    async def run_analysis_async(self, data: List[Dict[str, Any]], 
                                analyzer_names: Optional[List[str]] = None,
                                task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        异步运行分析
        
        Args:
            data: 预处理后的数据
            analyzer_names: 要运行的分析器列表
            task_id: 任务ID（用于进度更新）
            
        Returns:
            分析结果
        """
        if analyzer_names is None:
            analyzer_names = self.analyzer_registry.get_available_analyzers()

        logger.info(f"开始异步分析，分析器: {analyzer_names}")

        try:
            # 验证分析器名称
            available_analyzers = self.analyzer_registry.get_available_analyzers()
            invalid_analyzers = [name for name in analyzer_names if name not in available_analyzers]
            if invalid_analyzers:
                raise ValueError(f"未知的分析器: {invalid_analyzers}")
            
            # 并发执行分析器
            results = await self._run_analyzers_concurrent(data, analyzer_names, task_id)
            
            # 添加元数据
            results['metadata'] = {
                'data_count': len(data),
                'analyzers_used': analyzer_names,
                'analysis_completed_at': datetime.now().isoformat(),
                'processing_method': 'async_concurrent'
            }
            
            logger.info("异步分析完成")
            return results
            
        except Exception as e:
            logger.error(f"异步分析失败: {e}")
            raise
    
    def run_analysis_sync(self, data: List[Dict[str, Any]], 
                         analyzer_names: Optional[List[str]] = None,
                         task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        同步运行分析
        
        Args:
            data: 预处理后的数据
            analyzer_names: 要运行的分析器列表
            task_id: 任务ID（用于进度更新）
            
        Returns:
            分析结果
        """
        if analyzer_names is None:
            analyzer_names = self.analyzer_registry.get_available_analyzers()

        logger.info(f"开始同步分析，分析器: {analyzer_names}")

        try:
            # 验证分析器名称
            available_analyzers = self.analyzer_registry.get_available_analyzers()
            invalid_analyzers = [name for name in analyzer_names if name not in available_analyzers]
            if invalid_analyzers:
                raise ValueError(f"未知的分析器: {invalid_analyzers}")
            
            # 顺序执行分析器
            results = self._run_analyzers_sequential(data, analyzer_names, task_id)
            
            # 添加元数据
            results['metadata'] = {
                'data_count': len(data),
                'analyzers_used': analyzer_names,
                'analysis_completed_at': datetime.now().isoformat(),
                'processing_method': 'sync_sequential'
            }
            
            logger.info("同步分析完成")
            return results
            
        except Exception as e:
            logger.error(f"同步分析失败: {e}")
            raise
    
    async def _run_analyzers_concurrent(self, data: List[Dict[str, Any]], 
                                       analyzer_names: List[str],
                                       task_id: Optional[str]) -> Dict[str, Any]:
        """并发运行分析器"""
        loop = asyncio.get_event_loop()
        
        # 创建分析任务
        tasks = []
        for analyzer_name in analyzer_names:
            task = loop.run_in_executor(
                self.executor,
                self._run_single_analyzer,
                analyzer_name,
                data,
                task_id
            )
            tasks.append((analyzer_name, task))
        
        # 等待所有任务完成
        results = {}
        completed_count = 0
        total_count = len(tasks)
        
        for analyzer_name, task in tasks:
            try:
                result = await task
                results[analyzer_name] = result
                completed_count += 1
                
                # 更新进度
                if task_id:
                    progress = 20 + (completed_count / total_count) * 60  # 分析阶段占20-80%
                    self._update_progress(task_id, progress, f"{analyzer_name} 分析完成")
                
            except Exception as e:
                logger.error(f"分析器 {analyzer_name} 执行失败: {e}")
                results[analyzer_name] = {'error': str(e)}
        
        return results
    
    def _run_analyzers_sequential(self, data: List[Dict[str, Any]], 
                                 analyzer_names: List[str],
                                 task_id: Optional[str]) -> Dict[str, Any]:
        """顺序运行分析器"""
        results = {}
        total_count = len(analyzer_names)
        
        for i, analyzer_name in enumerate(analyzer_names):
            try:
                # 更新进度
                if task_id:
                    progress = 20 + (i / total_count) * 60  # 分析阶段占20-80%
                    self._update_progress(task_id, progress, f"正在运行 {analyzer_name} 分析器...")
                
                result = self._run_single_analyzer(analyzer_name, data, task_id)
                results[analyzer_name] = result
                
                # 更新完成进度
                if task_id:
                    progress = 20 + ((i + 1) / total_count) * 60
                    self._update_progress(task_id, progress, f"{analyzer_name} 分析完成")
                
            except Exception as e:
                logger.error(f"分析器 {analyzer_name} 执行失败: {e}")
                results[analyzer_name] = {'error': str(e)}
        
        return results
    
    def _run_single_analyzer(self, analyzer_name: str, data: List[Dict[str, Any]], 
                           task_id: Optional[str]) -> Dict[str, Any]:
        """运行单个分析器"""
        logger.info(f"开始运行分析器: {analyzer_name}")
        
        try:
            analyzer = self.analyzer_registry.get_analyzer(analyzer_name)
            
            # 记录开始时间
            start_time = datetime.now()
            
            # 执行分析
            result = analyzer.run(data)
            
            # 记录结束时间
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # 添加执行信息
            result['execution_info'] = {
                'analyzer_name': analyzer_name,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'execution_time_seconds': execution_time,
                'data_count': len(data)
            }
            
            logger.info(f"分析器 {analyzer_name} 执行完成，耗时: {execution_time:.2f}秒")
            return result
            
        except Exception as e:
            logger.error(f"分析器 {analyzer_name} 执行失败: {e}")
            raise
    
    def _update_progress(self, task_id: str, progress: float, message: str):
        """更新任务进度"""
        try:
            from core.task_queue import get_task_queue
            task_queue = get_task_queue()
            task_queue.update_task_progress(task_id, progress, message)
            
        except Exception as e:
            logger.warning(f"更新进度失败: {e}")
    
    def get_available_analyzers(self) -> List[str]:
        """获取可用的分析器列表"""
        return self.analyzer_registry.get_available_analyzers()

    def get_analyzer_info(self, analyzer_name: str) -> Dict[str, Any]:
        """获取分析器信息"""
        return self.analyzer_registry.get_analyzer_info(analyzer_name)
    
    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        available_analyzers = self.get_available_analyzers()
        return {
            'service_name': 'AnalysisService',
            'max_workers': self.max_workers,
            'available_analyzers': available_analyzers,
            'analyzer_count': len(available_analyzers),
            'active_threads': len(self.executor._threads) if hasattr(self.executor, '_threads') else 0,
            'registry_stats': self.analyzer_registry.get_registry_stats()
        }
    
    def shutdown(self):
        """关闭服务"""
        self.executor.shutdown(wait=True)
        logger.info("分析服务已关闭")


# 全局分析服务实例
analysis_service = AnalysisService()


def get_analysis_service() -> AnalysisService:
    """获取分析服务实例"""
    return analysis_service
