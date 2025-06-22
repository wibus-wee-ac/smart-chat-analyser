"""
API使用示例
演示如何使用聊天记录分析器的API
"""

import requests
import json
import time
import socketio
from typing import Dict, Any

class ChatlogAnalyzerClient:
    """聊天记录分析器客户端"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        """
        初始化客户端
        
        Args:
            base_url: 服务器地址
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/v1"
        
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        response = requests.get(f"{self.api_base}/health")
        response.raise_for_status()
        return response.json()
    
    def submit_analysis_task(self, talker: str = None, days: int = 30, 
                           analyzers: list = None, limit: int = None) -> str:
        """
        提交分析任务
        
        Args:
            talker: 聊天对象
            days: 分析天数
            analyzers: 分析器列表
            limit: 记录数量限制
            
        Returns:
            任务ID
        """
        task_data = {}
        
        if talker:
            task_data['talker'] = talker
            task_data['days'] = days
        elif limit:
            task_data['limit'] = limit
        else:
            raise ValueError("必须提供 talker 或 limit 参数")
        
        if analyzers:
            task_data['analyzers'] = analyzers
        
        payload = {
            'task_type': 'chatlog_analysis',
            'task_data': task_data
        }
        
        response = requests.post(f"{self.api_base}/tasks", json=payload)
        response.raise_for_status()
        
        result = response.json()
        return result['task_id']
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        response = requests.get(f"{self.api_base}/tasks/{task_id}")
        response.raise_for_status()
        return response.json()
    
    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """获取任务结果"""
        response = requests.get(f"{self.api_base}/tasks/{task_id}/result")
        response.raise_for_status()
        return response.json()
    
    def wait_for_task_completion(self, task_id: str, timeout: int = 300) -> Dict[str, Any]:
        """
        等待任务完成
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
            
        Returns:
            任务结果
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_task_status(task_id)
            
            print(f"任务状态: {status['status']} - 进度: {status['progress']:.1f}% - {status['message']}")
            
            if status['status'] == 'completed':
                return self.get_task_result(task_id)
            elif status['status'] == 'failed':
                raise RuntimeError(f"任务失败: {status.get('error', '未知错误')}")
            elif status['status'] == 'cancelled':
                raise RuntimeError("任务已取消")
            
            time.sleep(2)
        
        raise TimeoutError(f"任务超时: {task_id}")
    
    def get_available_analyzers(self) -> Dict[str, Any]:
        """获取可用分析器"""
        response = requests.get(f"{self.api_base}/analyzers")
        response.raise_for_status()
        return response.json()
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计"""
        response = requests.get(f"{self.api_base}/system/stats")
        response.raise_for_status()
        return response.json()

class WebSocketClient:
    """WebSocket客户端示例"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.sio = socketio.Client()
        self.base_url = base_url
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置事件处理器"""
        
        @self.sio.event
        def connect():
            print("✅ WebSocket连接成功")
        
        @self.sio.event
        def disconnect():
            print("❌ WebSocket连接断开")
        
        @self.sio.event
        def connected(data):
            print(f"🔗 服务器确认连接: {data}")
        
        @self.sio.event
        def task_update(data):
            """任务更新事件"""
            update_type = data.get('type', 'unknown')
            task_id = data.get('task_id', 'unknown')
            
            if update_type == 'progress':
                progress = data.get('progress', 0)
                message = data.get('message', '')
                print(f"📊 任务进度 {task_id}: {progress:.1f}% - {message}")
                
            elif update_type == 'completion':
                status = data.get('status', 'unknown')
                print(f"✅ 任务完成 {task_id}: {status}")
                
            elif update_type == 'status':
                status = data.get('status', 'unknown')
                progress = data.get('progress', 0)
                print(f"📋 任务状态 {task_id}: {status} ({progress:.1f}%)")
        
        @self.sio.event
        def error(data):
            print(f"❌ 错误: {data}")
    
    def connect(self):
        """连接WebSocket"""
        self.sio.connect(self.base_url)
    
    def disconnect(self):
        """断开WebSocket"""
        self.sio.disconnect()
    
    def subscribe_task(self, task_id: str):
        """订阅任务更新"""
        self.sio.emit('subscribe_task', {'task_id': task_id})
        print(f"📡 已订阅任务: {task_id}")
    
    def unsubscribe_task(self, task_id: str):
        """取消订阅任务"""
        self.sio.emit('unsubscribe_task', {'task_id': task_id})
        print(f"📡 已取消订阅任务: {task_id}")

def example_basic_usage():
    """基础使用示例"""
    print("=== 基础使用示例 ===")
    
    client = ChatlogAnalyzerClient()
    
    # 1. 健康检查
    print("1. 健康检查...")
    health = client.health_check()
    print(f"服务状态: {health['status']}")
    
    # 2. 获取可用分析器
    print("\n2. 获取可用分析器...")
    analyzers = client.get_available_analyzers()
    print(f"可用分析器: {analyzers['analyzers']}")
    
    # 3. 提交分析任务
    print("\n3. 提交分析任务...")
    task_id = client.submit_analysis_task(
        limit=100,  # 分析最近100条记录
        analyzers=['word_frequency', 'sentiment']  # 只运行词频和情感分析
    )
    print(f"任务ID: {task_id}")
    
    # 4. 等待任务完成
    print("\n4. 等待任务完成...")
    try:
        result = client.wait_for_task_completion(task_id)
        print("✅ 任务完成!")
        
        # 5. 查看结果摘要
        print("\n5. 结果摘要:")
        analysis_results = result['result']['analysis_results']
        
        if 'word_frequency' in analysis_results:
            wf_result = analysis_results['word_frequency']
            print(f"  词频分析: 总词数 {wf_result.get('total_words', 0)}, 唯一词数 {wf_result.get('unique_words', 0)}")
        
        if 'sentiment' in analysis_results:
            sentiment_result = analysis_results['sentiment']
            sentiment_dist = sentiment_result.get('sentiment_distribution', {})
            print(f"  情感分析: {sentiment_dist}")
        
        # 6. 查看图表数据
        chart_data = result['result']['chart_data']
        print(f"\n6. 生成图表: {len(chart_data)} 个分析器的图表")
        
    except Exception as e:
        print(f"❌ 任务执行失败: {e}")

def example_websocket_usage():
    """WebSocket使用示例"""
    print("\n=== WebSocket使用示例 ===")
    
    # 创建客户端
    api_client = ChatlogAnalyzerClient()
    ws_client = WebSocketClient()
    
    try:
        # 连接WebSocket
        ws_client.connect()
        
        # 提交任务
        print("提交分析任务...")
        task_id = api_client.submit_analysis_task(limit=50)
        print(f"任务ID: {task_id}")
        
        # 订阅任务更新
        ws_client.subscribe_task(task_id)
        
        # 等待任务完成（通过WebSocket接收更新）
        print("等待任务完成（通过WebSocket接收实时更新）...")
        time.sleep(30)  # 等待30秒
        
        # 取消订阅
        ws_client.unsubscribe_task(task_id)
        
    finally:
        ws_client.disconnect()

def example_system_monitoring():
    """系统监控示例"""
    print("\n=== 系统监控示例 ===")
    
    client = ChatlogAnalyzerClient()
    
    # 获取系统统计
    stats = client.get_system_stats()
    
    print("系统状态:")
    print(f"  任务队列: {stats['task_queue']['queue_length']} 个待处理任务")
    print(f"  已加载模型: {stats['model_manager']['model_count']} 个")
    print(f"  可用分析器: {stats['analysis_service']['analyzer_count']} 个")

if __name__ == '__main__':
    try:
        # 基础使用示例
        example_basic_usage()
        
        # WebSocket使用示例
        example_websocket_usage()
        
        # 系统监控示例
        example_system_monitoring()
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保服务正在运行")
    except Exception as e:
        print(f"❌ 示例执行失败: {e}")
