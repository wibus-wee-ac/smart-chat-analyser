"""
WebSocket管理器
处理实时进度推送和任务状态通知
"""

import logging
import json
import threading
from typing import Dict, Any, Optional, Set
from datetime import datetime
import redis
from flask_socketio import join_room, leave_room

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket管理器"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        初始化WebSocket管理器
        
        Args:
            redis_url: Redis连接URL
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.socketio = None
        
        # 订阅者管理
        self.task_subscribers: Dict[str, Set[str]] = {}  # task_id -> set of session_ids
        self.subscriber_tasks: Dict[str, Set[str]] = {}  # session_id -> set of task_ids
        
        # Redis订阅线程
        self.pubsub = None
        self.subscription_thread = None
        self.is_running = False
        
        logger.info("WebSocket管理器初始化完成")
    
    def set_socketio(self, socketio):
        """设置SocketIO实例"""
        self.socketio = socketio
        self._setup_event_handlers()
        logger.info("SocketIO实例已设置")
    
    def start_redis_subscription(self):
        """启动Redis订阅"""
        if self.is_running:
            logger.warning("Redis订阅已在运行")
            return
        
        try:
            self.pubsub = self.redis_client.pubsub()
            
            # 订阅所有任务相关频道
            self.pubsub.psubscribe('task_progress:*')
            self.pubsub.psubscribe('task_completion:*')
            
            self.is_running = True
            self.subscription_thread = threading.Thread(
                target=self._redis_subscription_loop, 
                daemon=True
            )
            self.subscription_thread.start()
            
            logger.info("Redis订阅已启动")
            
        except Exception as e:
            logger.error(f"启动Redis订阅失败: {e}")
            raise
    
    def stop_redis_subscription(self):
        """停止Redis订阅"""
        self.is_running = False
        
        if self.pubsub:
            self.pubsub.close()
        
        if self.subscription_thread:
            self.subscription_thread.join(timeout=5)
        
        logger.info("Redis订阅已停止")
    
    def _redis_subscription_loop(self):
        """Redis订阅循环"""
        logger.info("Redis订阅循环已启动")
        
        try:
            for message in self.pubsub.listen():
                if not self.is_running:
                    break
                
                if message['type'] == 'pmessage':
                    self._handle_redis_message(message)
                    
        except Exception as e:
            logger.error(f"Redis订阅循环错误: {e}")
        finally:
            logger.info("Redis订阅循环已结束")
    
    def _handle_redis_message(self, message):
        """处理Redis消息"""
        try:
            channel = message['channel']
            data = json.loads(message['data'])
            
            if channel.startswith('task_progress:'):
                task_id = channel.split(':', 1)[1]
                self._broadcast_task_progress(task_id, data)
                
            elif channel.startswith('task_completion:'):
                task_id = channel.split(':', 1)[1]
                self._broadcast_task_completion(task_id, data)
                
        except Exception as e:
            logger.error(f"处理Redis消息失败: {e}")
    
    def _broadcast_task_progress(self, task_id: str, data: Dict[str, Any]):
        """广播任务进度更新"""
        if not self.socketio:
            return
        
        # 向订阅该任务的客户端发送进度更新
        room = f"task_{task_id}"
        
        progress_data = {
            'type': 'progress',
            'task_id': task_id,
            'progress': data.get('progress', 0),
            'message': data.get('message', ''),
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
        
        self.socketio.emit('task_update', progress_data, room=room)
        logger.debug(f"广播任务进度: {task_id} - {data.get('progress', 0)}%")
    
    def _broadcast_task_completion(self, task_id: str, data: Dict[str, Any]):
        """广播任务完成"""
        if not self.socketio:
            return
        
        room = f"task_{task_id}"
        
        completion_data = {
            'type': 'completion',
            'task_id': task_id,
            'status': data.get('status', 'unknown'),
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
        
        self.socketio.emit('task_update', completion_data, room=room)
        logger.info(f"广播任务完成: {task_id} - {data.get('status', 'unknown')}")
        
        # 清理订阅者
        self._cleanup_task_subscribers(task_id)
    
    def _setup_event_handlers(self):
        """设置SocketIO事件处理器"""
        if not self.socketio:
            return
        
        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """客户端连接"""
            from flask import request
            session_id = request.sid
            logger.info(f"客户端连接: {session_id}")

            # 初始化订阅者记录
            self.subscriber_tasks[session_id] = set()

            self.socketio.emit('connected', {
                'message': '连接成功',
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            })

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客户端断开连接"""
            from flask import request
            session_id = request.sid
            logger.info(f"客户端断开连接: {session_id}")

            # 清理订阅记录
            self._cleanup_session_subscriptions(session_id)
        
        @self.socketio.on('subscribe_task')
        def handle_subscribe_task(data):
            """订阅任务进度更新"""
            from flask import request
            session_id = request.sid
            task_id = data.get('task_id')

            if not task_id:
                self.socketio.emit('error', {'message': '缺少task_id参数'})
                return

            # 加入任务房间
            join_room(f"task_{task_id}")

            # 记录订阅关系
            if task_id not in self.task_subscribers:
                self.task_subscribers[task_id] = set()
            self.task_subscribers[task_id].add(session_id)
            self.subscriber_tasks[session_id].add(task_id)

            logger.info(f"客户端 {session_id} 订阅任务: {task_id}")

            # 发送当前任务状态
            self._send_current_task_status(session_id, task_id)

        @self.socketio.on('unsubscribe_task')
        def handle_unsubscribe_task(data):
            """取消订阅任务进度更新"""
            from flask import request
            session_id = request.sid
            task_id = data.get('task_id')

            if not task_id:
                self.socketio.emit('error', {'message': '缺少task_id参数'})
                return

            # 离开任务房间
            leave_room(f"task_{task_id}")

            # 清理订阅关系
            if task_id in self.task_subscribers:
                self.task_subscribers[task_id].discard(session_id)
                if not self.task_subscribers[task_id]:
                    del self.task_subscribers[task_id]

            if session_id in self.subscriber_tasks:
                self.subscriber_tasks[session_id].discard(task_id)

            logger.info(f"客户端 {session_id} 取消订阅任务: {task_id}")

        @self.socketio.on('get_task_status')
        def handle_get_task_status(data):
            """获取任务状态"""
            from flask import request
            session_id = request.sid
            task_id = data.get('task_id')

            if not task_id:
                self.socketio.emit('error', {'message': '缺少task_id参数'})
                return

            self._send_current_task_status(session_id, task_id)
    
    def _send_current_task_status(self, session_id: str, task_id: str):
        """发送当前任务状态"""
        try:
            from core.task_queue import get_task_queue
            task_queue = get_task_queue()
            
            task_info = task_queue.get_task_status(task_id)
            if task_info:
                status_data = {
                    'type': 'status',
                    'task_id': task_id,
                    'status': task_info.status.value,
                    'progress': task_info.progress,
                    'message': task_info.message,
                    'created_at': task_info.created_at.isoformat(),
                    'started_at': task_info.started_at.isoformat() if task_info.started_at else None,
                    'completed_at': task_info.completed_at.isoformat() if task_info.completed_at else None
                }
                
                self.socketio.emit('task_update', status_data, room=session_id)
            else:
                self.socketio.emit('error', {'message': '任务不存在'}, room=session_id)
                
        except Exception as e:
            logger.error(f"发送任务状态失败: {e}")
            self.socketio.emit('error', {'message': '获取任务状态失败'}, room=session_id)
    
    def _cleanup_session_subscriptions(self, session_id: str):
        """清理会话的所有订阅"""
        if session_id in self.subscriber_tasks:
            task_ids = self.subscriber_tasks[session_id].copy()
            
            for task_id in task_ids:
                if task_id in self.task_subscribers:
                    self.task_subscribers[task_id].discard(session_id)
                    if not self.task_subscribers[task_id]:
                        del self.task_subscribers[task_id]
            
            del self.subscriber_tasks[session_id]
    
    def _cleanup_task_subscribers(self, task_id: str):
        """清理任务的所有订阅者"""
        if task_id in self.task_subscribers:
            session_ids = self.task_subscribers[task_id].copy()
            
            for session_id in session_ids:
                if session_id in self.subscriber_tasks:
                    self.subscriber_tasks[session_id].discard(task_id)
            
            del self.task_subscribers[task_id]
    
    def get_subscription_stats(self) -> Dict[str, Any]:
        """获取订阅统计信息"""
        return {
            'active_tasks': len(self.task_subscribers),
            'active_sessions': len(self.subscriber_tasks),
            'total_subscriptions': sum(len(subscribers) for subscribers in self.task_subscribers.values()),
            'redis_subscription_running': self.is_running
        }


# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    """获取WebSocket管理器实例"""
    return websocket_manager
