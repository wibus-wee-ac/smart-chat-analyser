#!/usr/bin/env python3
"""
Flask-RESTX API 客户端使用示例
演示如何使用新的 API 接口
"""

import requests
import json
import time
from typing import Dict, Any, Optional

class ChatlogAnalyzerClient:
    """聊天记录分析器 API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:5031"):
        """
        初始化客户端
        
        Args:
            base_url: API 基础URL
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/v1"
        
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        response = requests.get(f"{self.api_base}/health")
        response.raise_for_status()
        return response.json()
    
    def submit_task(self, task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提交分析任务
        
        Args:
            task_type: 任务类型
            task_data: 任务数据
            
        Returns:
            任务提交响应
        """
        payload = {
            "task_type": task_type,
            "task_data": task_data
        }
        
        response = requests.post(
            f"{self.api_base}/tasks",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()
    
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
    
    def get_tasks(self, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """获取任务列表"""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
            
        response = requests.get(f"{self.api_base}/tasks", params=params)
        response.raise_for_status()
        return response.json()
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """取消任务"""
        response = requests.post(f"{self.api_base}/tasks/{task_id}/cancel")
        response.raise_for_status()
        return response.json()
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        response = requests.get(f"{self.api_base}/queue/stats")
        response.raise_for_status()
        return response.json()
    
    def get_analyzers(self) -> Dict[str, Any]:
        """获取可用分析器"""
        response = requests.get(f"{self.api_base}/analyzers")
        response.raise_for_status()
        return response.json()
    
    def get_analyzer_info(self, analyzer_name: str) -> Dict[str, Any]:
        """获取分析器信息"""
        response = requests.get(f"{self.api_base}/analyzers/{analyzer_name}")
        response.raise_for_status()
        return response.json()
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        response = requests.get(f"{self.api_base}/models/info")
        response.raise_for_status()
        return response.json()
    
    def preload_model(self, model_key: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """预加载模型"""
        payload = {"force": force}
        if model_key:
            payload["model_key"] = model_key
            
        response = requests.post(
            f"{self.api_base}/models/preload",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()
    
    def search_users(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """搜索用户"""
        params = {"q": query, "limit": limit}
        response = requests.get(f"{self.api_base}/user-cache/search", params=params)
        response.raise_for_status()
        return response.json()
    
    def wait_for_task_completion(self, task_id: str, timeout: int = 300, poll_interval: int = 5) -> Dict[str, Any]:
        """
        等待任务完成
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
            
        Returns:
            任务结果
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_task_status(task_id)
            
            if status.get('status') == 'completed':
                return self.get_task_result(task_id)
            elif status.get('status') in ['failed', 'cancelled']:
                raise Exception(f"任务失败: {status.get('message', '未知错误')}")
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"任务 {task_id} 在 {timeout} 秒内未完成")

def main():
    """示例用法"""
    # 创建客户端
    client = ChatlogAnalyzerClient()
    
    try:
        # 1. 健康检查
        print("1. 健康检查...")
        health = client.health_check()
        print(f"服务状态: {health['status']}")
        print(f"版本: {health['version']}")
        
        # 2. 获取可用分析器
        print("\n2. 获取可用分析器...")
        analyzers = client.get_analyzers()
        print(f"可用分析器: {analyzers['analyzers']}")
        
        # 3. 获取队列统计
        print("\n3. 获取队列统计...")
        stats = client.get_queue_stats()
        print(f"队列统计: {json.dumps(stats['queue'], indent=2, ensure_ascii=False)}")
        
        # 4. 提交分析任务
        print("\n4. 提交分析任务...")
        task_data = {
            "talker": "测试用户",
            "limit": 100
        }
        
        task_response = client.submit_task("chatlog_analysis", task_data)
        task_id = task_response['task_id']
        print(f"任务已提交: {task_id}")
        
        # 5. 查询任务状态
        print("\n5. 查询任务状态...")
        status = client.get_task_status(task_id)
        print(f"任务状态: {status['status']}")
        
        # 6. 获取任务列表
        print("\n6. 获取任务列表...")
        tasks = client.get_tasks(limit=5)
        print(f"任务总数: {tasks['pagination']['total']}")
        print(f"最近任务数: {len(tasks['tasks'])}")
        
        # 7. 模型信息
        print("\n7. 获取模型信息...")
        model_info = client.get_model_info()
        print(f"已加载模型: {model_info.get('loaded_models', [])}")
        
        print("\n✅ API 测试完成！")
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保服务已启动")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 错误: {e}")
        if e.response:
            try:
                error_detail = e.response.json()
                print(f"错误详情: {error_detail}")
            except:
                print(f"响应内容: {e.response.text}")
    except Exception as e:
        print(f"❌ 其他错误: {e}")

if __name__ == '__main__':
    main()
