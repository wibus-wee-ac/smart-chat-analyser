"""
分析任务处理器
处理聊天记录分析任务，集成所有分析器
"""

import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from core.task_queue import get_task_queue
from core.model_manager import get_model_manager
from services.data_preprocessing_service import get_data_preprocessing_service
from services.analysis_service import get_analysis_service
from services.visualization_service import get_visualization_service
from chatlog_client import ChatlogClient

logger = logging.getLogger(__name__)

class AnalysisTaskHandler:
    """分析任务处理器"""
    
    def __init__(self):
        self.task_queue = get_task_queue()
        self.model_manager = get_model_manager()
        self.preprocessing_service = get_data_preprocessing_service()
        self.analysis_service = get_analysis_service()
        self.visualization_service = get_visualization_service()

        # 注册任务处理器
        self.task_queue.register_handler("chatlog_analysis", self.handle_analysis_task)

        logger.info("分析任务处理器初始化完成")
    
    async def handle_analysis_task(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理聊天记录分析任务
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            
        Returns:
            分析结果
        """
        logger.info(f"开始处理分析任务: {task_id}")
        
        try:
            # 解析任务参数
            talker = task_data.get('talker')
            days = task_data.get('days', 30)
            analyzers = task_data.get('analyzers', ['word_frequency', 'sentiment', 'time_pattern', 'social_network'])
            
            # 更新进度：开始获取数据
            self.task_queue.update_task_progress(task_id, 10.0, "正在获取聊天记录...")
            
            # 创建客户端
            client = ChatlogClient()

            # 获取聊天记录
            if talker:
                data = client.get_chatlog_by_talker(talker, days)
            else:
                data = client.get_chatlog(limit=task_data.get('limit', 1000))

            if not data:
                raise ValueError("未获取到聊天记录数据")

            # 更新进度：开始数据预处理
            self.task_queue.update_task_progress(task_id, 15.0, f"获取到 {len(data)} 条记录，开始数据预处理...")

            # 数据预处理（使用新的服务架构）
            preprocessing_result = await self.preprocessing_service.preprocess_data_async(data, task_id)
            filtered_data = preprocessing_result['filtered_data']

            # 更新进度：开始分析
            self.task_queue.update_task_progress(task_id, 20.0, f"预处理完成，开始分析 {len(filtered_data)} 条有效记录...")

            # 执行分析（使用新的服务架构）
            results = await self.analysis_service.run_analysis_async(filtered_data, analyzers, task_id)

            # 更新进度：生成可视化
            self.task_queue.update_task_progress(task_id, 90.0, "正在生成可视化图表...")

            # 生成可视化图表（返回JSON数据而不是文件）
            chart_data = self.visualization_service.generate_charts(results)
            
            # 组装最终结果
            final_result = {
                "analysis_results": results,
                "chart_data": chart_data,
                "metadata": {
                    "task_id": task_id,
                    "data_count": len(data),
                    "analyzers_used": analyzers,
                    "completed_at": datetime.now().isoformat()
                }
            }
            
            # 更新进度：完成
            self.task_queue.update_task_progress(task_id, 100.0, "分析完成")
            
            logger.info(f"分析任务完成: {task_id}")
            return final_result
            
        except Exception as e:
            logger.error(f"分析任务失败: {task_id}, 错误: {e}")
            raise
    





# 初始化任务处理器
analysis_task_handler = AnalysisTaskHandler()


def get_analysis_task_handler() -> AnalysisTaskHandler:
    """获取分析任务处理器实例"""
    return analysis_task_handler
