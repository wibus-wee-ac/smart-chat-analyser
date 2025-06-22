#!/usr/bin/env python3
"""
模型预加载功能示例
演示如何使用模型预加载API
"""

import requests
import time
import json
from typing import Dict, Any

class ModelPreloadClient:
    """模型预加载客户端"""
    
    def __init__(self, base_url: str = "http://localhost:6142"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/v1"
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        response = requests.get(f"{self.api_base}/models/info")
        return response.json()
    
    def preload_model(self, model_key: str, force: bool = False) -> Dict[str, Any]:
        """预加载指定模型"""
        data = {"model_key": model_key, "force": force}
        response = requests.post(f"{self.api_base}/models/preload", json=data)
        return response.json()
    
    def preload_all_models(self, force: bool = False) -> Dict[str, Any]:
        """预加载所有模型"""
        data = {"force": force}
        response = requests.post(f"{self.api_base}/models/preload", json=data)
        return response.json()
    
    def get_preload_status(self, model_key: str = None) -> Dict[str, Any]:
        """获取预加载状态"""
        params = {"model_key": model_key} if model_key else {}
        response = requests.get(f"{self.api_base}/models/preload/status", params=params)
        return response.json()
    
    def cancel_preload(self, model_key: str) -> Dict[str, Any]:
        """取消预加载"""
        data = {"model_key": model_key}
        response = requests.post(f"{self.api_base}/models/preload/cancel", json=data)
        return response.json()
    
    def clear_models(self, model_key: str = None) -> Dict[str, Any]:
        """清除模型"""
        data = {"model_key": model_key} if model_key else {}
        response = requests.post(f"{self.api_base}/models/clear", json=data)
        return response.json()

def main():
    """主函数"""
    client = ModelPreloadClient()
    
    print("=== 模型预加载功能演示 ===\n")
    
    try:
        # 1. 获取初始模型信息
        print("1. 获取初始模型信息:")
        info = client.get_model_info()
        print(json.dumps(info, indent=2, ensure_ascii=False))
        print()
        
        # 2. 获取预加载状态
        print("2. 获取预加载状态:")
        status = client.get_preload_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        print()
        
        # 3. 预加载情感分析模型
        print("3. 预加载情感分析模型:")
        result = client.preload_model("sentiment_model")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()
        
        # 4. 监控预加载进度
        print("4. 监控预加载进度:")
        for i in range(10):  # 最多等待10次
            status = client.get_preload_status("sentiment_model")
            print(f"进度: {status['status']['progress']:.1f}% - 状态: {status['status']['status']}")
            
            if status['status']['status'] in ['completed', 'failed']:
                break
                
            time.sleep(2)
        print()
        
        # 5. 预加载所有模型
        print("5. 预加载所有模型:")
        result = client.preload_all_models()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()
        
        # 6. 等待所有模型加载完成
        print("6. 等待所有模型加载完成:")
        for i in range(20):  # 最多等待20次
            status = client.get_preload_status()
            all_completed = True
            
            for model_key, model_status in status['status'].items():
                print(f"{model_key}: {model_status['progress']:.1f}% - {model_status['status']}")
                if model_status['status'] not in ['completed', 'failed']:
                    all_completed = False
            
            if all_completed:
                print("所有模型加载完成!")
                break
                
            print("---")
            time.sleep(3)
        print()
        
        # 7. 获取最终模型信息
        print("7. 获取最终模型信息:")
        info = client.get_model_info()
        print(json.dumps(info, indent=2, ensure_ascii=False))
        
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到服务器，请确保服务器正在运行")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    main()
