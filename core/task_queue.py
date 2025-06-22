"""
基于Redis的简单任务队列系统
支持异步任务执行、状态跟踪和进度更新
"""

import json
import uuid
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
import logging
import redis
from dataclasses import dataclass, asdict
import numpy as np

logger = logging.getLogger(__name__)


class TaskJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理特殊类型"""

    def default(self, obj):
        if isinstance(obj, bool):
            return obj  # bool类型在Python中是JSON原生支持的
        elif isinstance(obj, np.bool_):
            return bool(obj)  # numpy bool转换为Python bool
        elif isinstance(obj, np.integer):
            return int(obj)  # numpy整数转换为Python int
        elif isinstance(obj, np.floating):
            return float(obj)  # numpy浮点数转换为Python float
        elif isinstance(obj, np.ndarray):
            return obj.tolist()  # numpy数组转换为列表
        elif hasattr(obj, 'isoformat'):  # datetime对象
            return obj.isoformat()
        return super().default(obj)

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 正在执行
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 已取消

@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self, include_result: bool = True) -> Dict[str, Any]:
        """
        转换为字典

        Args:
            include_result: 是否包含result字段，默认True
        """
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None

        # 如果不需要包含result，则移除该字段
        if not include_result:
            data.pop('result', None)

        return data

class TaskQueue:
    """Redis任务队列"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        初始化任务队列
        
        Args:
            redis_url: Redis连接URL
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.queue_name = "chatlog_analysis_queue"
        self.task_prefix = "task:"
        self.result_prefix = "result:"
        self.progress_prefix = "progress:"
        
        # 任务处理器注册表
        self.task_handlers: Dict[str, Callable] = {}
        
        # 工作线程
        self.worker_thread = None
        self.is_running = False
        
        logger.info("任务队列初始化完成")
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self.task_handlers[task_type] = handler
        logger.info(f"注册任务处理器: {task_type}")
    
    def submit_task(self, task_type: str, task_data: Dict[str, Any]) -> str:
        """
        提交任务
        
        Args:
            task_type: 任务类型
            task_data: 任务数据
            
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        
        # 创建任务信息
        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        
        # 保存任务信息
        self._save_task_info(task_info)
        
        # 将任务加入队列
        task_payload = {
            "task_id": task_id,
            "task_type": task_type,
            "task_data": task_data
        }
        
        self.redis_client.lpush(self.queue_name, json.dumps(task_payload, cls=TaskJSONEncoder, ensure_ascii=False))
        
        logger.info(f"任务已提交: {task_id} ({task_type})")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        task_key = f"{self.task_prefix}{task_id}"
        task_data = self.redis_client.get(task_key)
        
        if not task_data:
            return None
        
        data = json.loads(task_data)
        
        # 重建TaskInfo对象
        task_info = TaskInfo(
            task_id=data['task_id'],
            task_type=data['task_type'],
            status=TaskStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data['started_at'] else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None,
            progress=data['progress'],
            message=data['message'],
            result=data['result'],
            error=data['error']
        )
        
        return task_info
    
    def update_task_progress(self, task_id: str, progress: float, message: str = ""):
        """更新任务进度"""
        task_info = self.get_task_status(task_id)
        if task_info:
            task_info.progress = progress
            task_info.message = message
            self._save_task_info(task_info)
            
            # 发布进度更新事件
            self._publish_progress_update(task_id, progress, message)
    
    def _save_task_info(self, task_info: TaskInfo):
        """保存任务信息"""
        task_key = f"{self.task_prefix}{task_info.task_id}"
        self.redis_client.setex(
            task_key,
            timedelta(hours=24),  # 24小时过期
            json.dumps(task_info.to_dict(), cls=TaskJSONEncoder, ensure_ascii=False)
        )
    
    def _publish_progress_update(self, task_id: str, progress: float, message: str):
        """发布进度更新"""
        update_data = {
            "task_id": task_id,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

        channel = f"task_progress:{task_id}"
        self.redis_client.publish(channel, json.dumps(update_data, cls=TaskJSONEncoder, ensure_ascii=False))
    
    def start_worker(self):
        """启动工作线程"""
        if self.is_running:
            logger.warning("工作线程已在运行")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("任务队列工作线程已启动")
    
    def stop_worker(self):
        """停止工作线程"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("任务队列工作线程已停止")
    
    def _worker_loop(self):
        """工作线程主循环"""
        while self.is_running:
            try:
                # 阻塞式获取任务（超时1秒）
                task_data = self.redis_client.brpop(self.queue_name, timeout=1)
                
                if task_data:
                    _, task_payload = task_data
                    self._process_task(json.loads(task_payload))
                    
            except Exception as e:
                logger.error(f"工作线程错误: {e}")
                time.sleep(1)
    
    def _process_task(self, task_payload: Dict[str, Any]):
        """处理单个任务"""
        task_id = task_payload["task_id"]
        task_type = task_payload["task_type"]
        task_data = task_payload["task_data"]

        logger.info(f"开始处理任务: {task_id} ({task_type})")

        # 更新任务状态为运行中
        task_info = self.get_task_status(task_id)
        if not task_info:
            logger.error(f"任务信息不存在: {task_id}")
            return

        task_info.status = TaskStatus.RUNNING
        task_info.started_at = datetime.now()
        self._save_task_info(task_info)

        try:
            # 查找并执行任务处理器
            if task_type not in self.task_handlers:
                raise ValueError(f"未知的任务类型: {task_type}")

            handler = self.task_handlers[task_type]

            # 检查处理器是否为异步函数
            import asyncio
            import inspect

            if inspect.iscoroutinefunction(handler):
                # 异步处理器
                result = asyncio.run(handler(task_id, task_data))
            else:
                # 同步处理器
                result = handler(task_id, task_data)

            # 任务完成
            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = datetime.now()
            task_info.result = result
            task_info.progress = 100.0
            task_info.message = "任务执行完成"

            logger.info(f"任务完成: {task_id}")

        except Exception as e:
            # 任务失败
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now()
            task_info.error = str(e)
            task_info.message = f"任务执行失败: {e}"

            logger.error(f"任务失败: {task_id}, 错误: {e}")

        finally:
            self._save_task_info(task_info)
            # 发布任务完成事件
            self._publish_task_completion(task_id, task_info.status)
    
    def _publish_task_completion(self, task_id: str, status: TaskStatus):
        """发布任务完成事件"""
        completion_data = {
            "task_id": task_id,
            "status": status.value,
            "timestamp": datetime.now().isoformat()
        }

        channel = f"task_completion:{task_id}"
        self.redis_client.publish(channel, json.dumps(completion_data, cls=TaskJSONEncoder, ensure_ascii=False))
    
    def get_all_tasks(self, status_filter: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[TaskInfo]:
        """
        获取所有任务列表

        Args:
            status_filter: 状态过滤器，可选值：pending, running, completed, failed, cancelled
            limit: 返回任务数量限制，默认100
            offset: 偏移量，用于分页，默认0

        Returns:
            任务信息列表
        """
        try:
            # 获取所有任务键
            task_keys = self.redis_client.keys(f"{self.task_prefix}*")

            if not task_keys:
                return []

            # 批量获取任务数据
            task_data_list = self.redis_client.mget(task_keys)

            tasks = []
            for task_data in task_data_list:
                if task_data:
                    try:
                        data = json.loads(task_data)

                        # 状态过滤
                        if status_filter and data.get('status') != status_filter:
                            continue

                        # 重建TaskInfo对象
                        task_info = TaskInfo(
                            task_id=data['task_id'],
                            task_type=data['task_type'],
                            status=TaskStatus(data['status']),
                            created_at=datetime.fromisoformat(data['created_at']),
                            started_at=datetime.fromisoformat(data['started_at']) if data['started_at'] else None,
                            completed_at=datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None,
                            progress=data['progress'],
                            message=data['message'],
                            result=data['result'],
                            error=data['error']
                        )

                        tasks.append(task_info)

                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning(f"解析任务数据失败: {e}")
                        continue

            # 按创建时间倒序排序（最新的在前面）
            tasks.sort(key=lambda x: x.created_at, reverse=True)

            # 分页处理
            start_idx = offset
            end_idx = offset + limit

            return tasks[start_idx:end_idx]

        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            return []

    def get_task_count(self, status_filter: Optional[str] = None) -> int:
        """
        获取任务总数

        Args:
            status_filter: 状态过滤器

        Returns:
            任务总数
        """
        try:
            if not status_filter:
                # 如果没有状态过滤器，直接返回任务键的数量
                task_keys = self.redis_client.keys(f"{self.task_prefix}*")
                return len(task_keys)

            # 有状态过滤器时，需要逐个检查
            task_keys = self.redis_client.keys(f"{self.task_prefix}*")
            if not task_keys:
                return 0

            task_data_list = self.redis_client.mget(task_keys)
            count = 0

            for task_data in task_data_list:
                if task_data:
                    try:
                        data = json.loads(task_data)
                        if data.get('status') == status_filter:
                            count += 1
                    except (json.JSONDecodeError, KeyError):
                        continue

            return count

        except Exception as e:
            logger.error(f"获取任务数量失败: {e}")
            return 0

    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        queue_length = self.redis_client.llen(self.queue_name)

        return {
            "queue_length": queue_length,
            "worker_running": self.is_running,
            "registered_handlers": list(self.task_handlers.keys())
        }


# 全局任务队列实例
task_queue = TaskQueue()


def get_task_queue() -> TaskQueue:
    """获取任务队列实例"""
    return task_queue
