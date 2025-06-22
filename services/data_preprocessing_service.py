"""
数据预处理服务
独立的数据预处理服务，确保在所有分析之前进行数据清洗和标准化
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from data_preprocessor import DataPreprocessor

logger = logging.getLogger(__name__)

class DataPreprocessingService:
    """数据预处理服务"""
    
    def __init__(self, max_workers: int = 4):
        """
        初始化数据预处理服务
        
        Args:
            max_workers: 最大工作线程数
        """
        self.preprocessor = DataPreprocessor()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        logger.info(f"数据预处理服务初始化完成，工作线程数: {max_workers}")
    
    async def preprocess_data_async(self, data: List[Dict[str, Any]], 
                                   task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        异步预处理数据
        
        Args:
            data: 原始聊天记录数据
            task_id: 任务ID（用于进度更新）
            
        Returns:
            预处理结果
        """
        logger.info(f"开始异步数据预处理，数据量: {len(data)}")
        
        try:
            # 在线程池中执行预处理
            loop = asyncio.get_event_loop()
            
            # 分批处理大数据集
            if len(data) > 10000:
                result = await self._preprocess_large_dataset(data, task_id, loop)
            else:
                result = await loop.run_in_executor(
                    self.executor,
                    self._preprocess_batch,
                    data,
                    task_id
                )
            
            logger.info("异步数据预处理完成")
            return result
            
        except Exception as e:
            logger.error(f"异步数据预处理失败: {e}")
            raise
    
    def preprocess_data_sync(self, data: List[Dict[str, Any]], 
                            task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        同步预处理数据
        
        Args:
            data: 原始聊天记录数据
            task_id: 任务ID（用于进度更新）
            
        Returns:
            预处理结果
        """
        logger.info(f"开始同步数据预处理，数据量: {len(data)}")
        
        try:
            result = self._preprocess_batch(data, task_id)
            logger.info("同步数据预处理完成")
            return result
            
        except Exception as e:
            logger.error(f"同步数据预处理失败: {e}")
            raise
    
    async def _preprocess_large_dataset(self, data: List[Dict[str, Any]], 
                                       task_id: Optional[str], 
                                       loop) -> Dict[str, Any]:
        """处理大数据集（分批处理）"""
        batch_size = 2000
        total_batches = (len(data) + batch_size - 1) // batch_size
        
        logger.info(f"大数据集分批处理，总批次: {total_batches}")
        
        all_filtered_data = []
        total_removed = 0
        
        # 创建批处理任务
        tasks = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_id = i // batch_size + 1
            
            task = loop.run_in_executor(
                self.executor,
                self._preprocess_batch,
                batch,
                f"{task_id}_batch_{batch_id}" if task_id else None
            )
            tasks.append(task)
        
        # 并发执行所有批次
        batch_results = await asyncio.gather(*tasks)
        
        # 合并结果
        for result in batch_results:
            all_filtered_data.extend(result['filtered_data'])
            total_removed += result['removed_count']
        
        # 计算最终统计
        original_count = len(data)
        filtered_count = len(all_filtered_data)
        removal_rate = (total_removed / original_count) * 100 if original_count > 0 else 0
        
        return {
            'filtered_data': all_filtered_data,
            'original_count': original_count,
            'filtered_count': filtered_count,
            'removed_count': total_removed,
            'removal_rate': removal_rate,
            'processing_method': 'batch_async'
        }
    
    def _preprocess_batch(self, data: List[Dict[str, Any]], 
                         task_id: Optional[str] = None) -> Dict[str, Any]:
        """预处理单个批次"""
        try:
            # 更新进度（如果有任务ID）
            if task_id:
                self._update_progress(task_id, "正在进行数据预处理...")
            
            # 执行预处理
            original_count = len(data)
            filtered_data = self.preprocessor.preprocess_data(data)
            
            # 计算统计信息
            filtered_count = len(filtered_data)
            removed_count = original_count - filtered_count
            removal_rate = (removed_count / original_count) * 100 if original_count > 0 else 0
            
            # 获取详细统计
            filter_stats = self.preprocessor.get_filter_stats(data, filtered_data)
            
            result = {
                'filtered_data': filtered_data,
                'original_count': original_count,
                'filtered_count': filtered_count,
                'removed_count': removed_count,
                'removal_rate': removal_rate,
                'filter_stats': filter_stats,
                'processing_method': 'single_batch'
            }
            
            logger.info(f"批次预处理完成: {original_count} -> {filtered_count} ({removal_rate:.1f}% 移除)")
            
            return result
            
        except Exception as e:
            logger.error(f"批次预处理失败: {e}")
            raise
    
    def _update_progress(self, task_id: str, message: str):
        """更新任务进度"""
        try:
            # 这里可以集成任务队列的进度更新
            from core.task_queue import get_task_queue
            task_queue = get_task_queue()
            
            # 预处理阶段通常占总进度的10-20%
            # 这里我们不更新具体进度，只更新消息
            logger.info(f"任务 {task_id}: {message}")
            
        except Exception as e:
            logger.warning(f"更新进度失败: {e}")
    
    def validate_input_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证输入数据格式"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'data_info': {}
        }
        
        try:
            if not isinstance(data, list):
                validation_result['is_valid'] = False
                validation_result['errors'].append("数据必须是列表格式")
                return validation_result
            
            if not data:
                validation_result['is_valid'] = False
                validation_result['errors'].append("数据为空")
                return validation_result
            
            # 检查数据结构
            required_fields = ['content', 'time']
            sample_size = min(10, len(data))
            
            for i, item in enumerate(data[:sample_size]):
                if not isinstance(item, dict):
                    validation_result['errors'].append(f"第{i+1}条数据不是字典格式")
                    continue
                
                for field in required_fields:
                    if field not in item:
                        validation_result['warnings'].append(f"第{i+1}条数据缺少字段: {field}")
            
            # 数据信息统计
            validation_result['data_info'] = {
                'total_count': len(data),
                'sample_checked': sample_size,
                'has_content': sum(1 for item in data[:sample_size] 
                                 if isinstance(item, dict) and item.get('content')),
                'has_time': sum(1 for item in data[:sample_size] 
                              if isinstance(item, dict) and item.get('time'))
            }
            
            if validation_result['errors']:
                validation_result['is_valid'] = False
            
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"验证过程出错: {e}")
        
        return validation_result
    
    def get_preprocessing_stats(self) -> Dict[str, Any]:
        """获取预处理服务统计信息"""
        return {
            'service_name': 'DataPreprocessingService',
            'max_workers': self.executor._max_workers,
            'active_threads': len(self.executor._threads) if hasattr(self.executor, '_threads') else 0,
            'preprocessor_config': {
                'min_content_length': self.preprocessor.min_content_length,
                'max_content_length': self.preprocessor.max_content_length,
                'garbage_patterns_count': len(self.preprocessor.garbage_patterns)
            }
        }
    
    def shutdown(self):
        """关闭服务"""
        self.executor.shutdown(wait=True)
        logger.info("数据预处理服务已关闭")


# 全局数据预处理服务实例
data_preprocessing_service = DataPreprocessingService()


def get_data_preprocessing_service() -> DataPreprocessingService:
    """获取数据预处理服务实例"""
    return data_preprocessing_service
