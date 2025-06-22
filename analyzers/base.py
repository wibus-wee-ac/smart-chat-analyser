"""
基础分析器类
定义所有分析器的统一接口协议
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """基础分析器抽象类"""
    
    def __init__(self, name: str, description: str = ""):
        """
        初始化分析器
        
        Args:
            name: 分析器名称
            description: 分析器描述
        """
        self.name = name
        self.description = description
        self.results = {}
        self.is_analyzed = False
    
    @abstractmethod
    def analyze(self, data: List[Dict]) -> Dict[str, Any]:
        """
        执行分析
        
        Args:
            data: 聊天记录数据列表
            
        Returns:
            分析结果字典
        """
        pass
    
    @abstractmethod
    def get_summary(self) -> Dict[str, Any]:
        """
        获取分析摘要
        
        Returns:
            分析摘要字典
        """
        pass
    
    def preprocess_data(self, data: List[Dict]) -> List[Dict]:
        """
        数据预处理
        
        Args:
            data: 原始数据
            
        Returns:
            预处理后的数据
        """
        # 过滤掉空内容的消息
        filtered_data = []
        for item in data:
            if isinstance(item, dict) and item.get('content'):
                filtered_data.append(item)
        
        logger.info(f"数据预处理完成，原始数据 {len(data)} 条，过滤后 {len(filtered_data)} 条")
        return filtered_data
    
    def validate_data(self, data: List[Dict]) -> bool:
        """
        验证数据格式
        
        Args:
            data: 待验证的数据
            
        Returns:
            数据是否有效
        """
        if not isinstance(data, list):
            logger.error("数据必须是列表格式")
            return False
        
        if not data:
            logger.warning("数据为空")
            return False
        
        # 检查必要字段
        required_fields = ['content', 'time']
        for item in data[:5]:  # 只检查前5条
            if not isinstance(item, dict):
                logger.error("数据项必须是字典格式")
                return False
            
            for field in required_fields:
                if field not in item:
                    logger.error(f"缺少必要字段: {field}")
                    return False
        
        return True
    
    def run(self, data: List[Dict]) -> Dict[str, Any]:
        """
        运行分析流程
        
        Args:
            data: 聊天记录数据
            
        Returns:
            分析结果
        """
        logger.info(f"开始运行分析器: {self.name}")
        
        # 数据验证
        if not self.validate_data(data):
            raise ValueError("数据格式无效")
        
        # 数据预处理
        processed_data = self.preprocess_data(data)
        
        # 执行分析
        self.results = self.analyze(processed_data)
        self.is_analyzed = True
        
        logger.info(f"分析器 {self.name} 运行完成")
        return self.results
    
    def export_results(self, format: str = "json") -> str:
        """
        导出分析结果
        
        Args:
            format: 导出格式 (json, csv, txt)
            
        Returns:
            导出内容
        """
        if not self.is_analyzed:
            raise RuntimeError("请先运行分析")
        
        if format == "json":
            import json
            import numpy as np

            # 自定义JSON编码器处理特殊类型
            class AnalyzerJSONEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, bool):
                        return obj
                    elif isinstance(obj, np.bool_):
                        return bool(obj)
                    elif isinstance(obj, np.integer):
                        return int(obj)
                    elif isinstance(obj, np.floating):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    elif hasattr(obj, 'isoformat'):
                        return obj.isoformat()
                    return super().default(obj)

            return json.dumps(self.results, cls=AnalyzerJSONEncoder, ensure_ascii=False, indent=2)
        elif format == "txt":
            summary = self.get_summary()
            lines = [f"分析器: {self.name}", f"描述: {self.description}", ""]
            for key, value in summary.items():
                lines.append(f"{key}: {value}")
            return "\n".join(lines)
        else:
            raise ValueError(f"不支持的导出格式: {format}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取分析统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "analyzer_name": self.name,
            "description": self.description,
            "is_analyzed": self.is_analyzed,
            "result_keys": list(self.results.keys()) if self.results else []
        } 