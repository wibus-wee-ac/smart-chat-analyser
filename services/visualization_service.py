"""
可视化服务
生成标准化的图表JSON数据，支持多种图表类型
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ChartDataStandardizer:
    """图表数据标准化器"""
    
    @staticmethod
    def create_chart_config(chart_type: str, title: str, data: Dict[str, Any], 
                           config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        创建标准化的图表配置
        
        Args:
            chart_type: 图表类型 (bar, line, pie, scatter, network, wordcloud)
            title: 图表标题
            data: 图表数据
            config: 额外配置
            
        Returns:
            标准化的图表配置
        """
        base_config = {
            "chart_id": f"{chart_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "chart_type": chart_type,
            "title": title,
            "data": data,
            "config": config or {},
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "data_points": ChartDataStandardizer._count_data_points(data),
                "chart_version": "1.0"
            }
        }
        
        return base_config
    
    @staticmethod
    def _count_data_points(data: Dict[str, Any]) -> int:
        """计算数据点数量"""
        if isinstance(data, dict):
            if 'values' in data:
                return len(data['values']) if isinstance(data['values'], list) else 1
            elif 'nodes' in data:
                return len(data['nodes']) if isinstance(data['nodes'], list) else 1
            else:
                return len(data)
        return 0

class VisualizationService:
    """可视化服务"""
    
    def __init__(self):
        self.standardizer = ChartDataStandardizer()
        logger.info("可视化服务初始化完成")
    
    def generate_charts(self, analysis_results: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        生成所有图表数据
        
        Args:
            analysis_results: 分析结果
            
        Returns:
            按分析器分组的图表数据
        """
        logger.info("开始生成图表数据")
        
        chart_data = {}
        
        try:
            for analyzer_name, result in analysis_results.items():
                if analyzer_name == 'metadata':
                    continue
                
                if isinstance(result, dict) and 'error' not in result:
                    charts = self._generate_analyzer_charts(analyzer_name, result)
                    if charts:
                        chart_data[analyzer_name] = charts
            
            logger.info(f"图表数据生成完成，共生成 {sum(len(charts) for charts in chart_data.values())} 个图表")
            
        except Exception as e:
            logger.error(f"生成图表数据失败: {e}")
            chart_data['error'] = str(e)
        
        return chart_data
    
    def _generate_analyzer_charts(self, analyzer_name: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """为特定分析器生成图表"""
        charts = []
        
        try:
            if analyzer_name == "word_frequency":
                charts.extend(self._create_word_frequency_charts(result))
            elif analyzer_name == "sentiment":
                charts.extend(self._create_sentiment_charts(result))
            elif analyzer_name == "time_pattern":
                charts.extend(self._create_time_pattern_charts(result))
            elif analyzer_name == "social_network":
                charts.extend(self._create_social_network_charts(result))
            
        except Exception as e:
            logger.error(f"生成 {analyzer_name} 图表失败: {e}")
        
        return charts
    
    def _create_word_frequency_charts(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建词频分析图表"""
        charts = []
        
        # 1. 高频词汇柱状图
        top_words = result.get('top_words', [])
        if top_words:
            chart_data = {
                "labels": [word for word, _ in top_words[:20]],
                "values": [count for _, count in top_words[:20]],
                "type": "bar"
            }
            
            config = {
                "xaxis": {"title": "词汇"},
                "yaxis": {"title": "频次"},
                "color_scheme": "viridis"
            }
            
            charts.append(self.standardizer.create_chart_config(
                "bar", "高频词汇统计", chart_data, config
            ))
        
        # 2. 词云数据
        word_freq_dist = result.get('word_frequency_distribution', {})
        if word_freq_dist:
            # 取前100个词用于词云
            sorted_words = sorted(word_freq_dist.items(), key=lambda x: x[1], reverse=True)[:100]
            
            chart_data = {
                "words": [{"text": word, "size": count} for word, count in sorted_words],
                "type": "wordcloud"
            }
            
            config = {
                "max_words": 100,
                "color_scheme": "Set3",
                "font_family": "Arial Unicode MS"
            }
            
            charts.append(self.standardizer.create_chart_config(
                "wordcloud", "词云图", chart_data, config
            ))
        
        # 3. 词性分布饼图
        word_by_type = result.get('word_by_type', {})
        if word_by_type:
            chart_data = {
                "labels": list(word_by_type.keys()),
                "values": [len(words) for words in word_by_type.values()],
                "type": "pie"
            }
            
            config = {
                "show_legend": True,
                "hole": 0.3  # 甜甜圈图
            }
            
            charts.append(self.standardizer.create_chart_config(
                "pie", "词性分布", chart_data, config
            ))
        
        return charts
    
    def _create_sentiment_charts(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建情感分析图表"""
        charts = []
        
        # 1. 情感分布饼图
        sentiment_dist = result.get('sentiment_distribution', {})
        if sentiment_dist:
            chart_data = {
                "labels": list(sentiment_dist.keys()),
                "values": list(sentiment_dist.values()),
                "type": "pie"
            }
            
            config = {
                "colors": {
                    "积极": "#2E8B57",
                    "消极": "#DC143C", 
                    "中性": "#708090"
                },
                "show_legend": True
            }
            
            charts.append(self.standardizer.create_chart_config(
                "pie", "情感分布", chart_data, config
            ))
        
        # 2. 情感时间序列
        detailed_results = result.get('detailed_results', [])
        if detailed_results:
            # 按时间聚合情感数据
            time_sentiment = self._aggregate_sentiment_by_time(detailed_results)
            
            if time_sentiment:
                chart_data = {
                    "x": list(time_sentiment.keys()),
                    "y": list(time_sentiment.values()),
                    "type": "line"
                }
                
                config = {
                    "xaxis": {"title": "时间"},
                    "yaxis": {"title": "平均情感分数"},
                    "line_color": "#1f77b4"
                }
                
                charts.append(self.standardizer.create_chart_config(
                    "line", "情感时间趋势", chart_data, config
                ))
        
        return charts
    
    def _create_time_pattern_charts(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建时间模式图表"""
        charts = []
        
        # 1. 小时分布柱状图
        hourly_stats = result.get('hourly_stats', {})
        if hourly_stats:
            chart_data = {
                "labels": [f"{hour:02d}:00" for hour in sorted(hourly_stats.keys())],
                "values": [hourly_stats[hour] for hour in sorted(hourly_stats.keys())],
                "type": "bar"
            }
            
            config = {
                "xaxis": {"title": "小时"},
                "yaxis": {"title": "消息数量"},
                "color_scheme": "plasma"
            }
            
            charts.append(self.standardizer.create_chart_config(
                "bar", "小时活跃度分布", chart_data, config
            ))
        
        # 2. 星期分布
        weekly_stats = result.get('weekly_stats', {})
        if weekly_stats:
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            
            chart_data = {
                "labels": weekday_names,
                "values": [weekly_stats.get(i, 0) for i in range(7)],
                "type": "bar"
            }
            
            config = {
                "xaxis": {"title": "星期"},
                "yaxis": {"title": "消息数量"},
                "color_scheme": "viridis"
            }
            
            charts.append(self.standardizer.create_chart_config(
                "bar", "星期活跃度分布", chart_data, config
            ))
        
        return charts
    
    def _create_social_network_charts(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建社交网络图表"""
        charts = []
        
        # 1. 网络图
        viz_data = result.get('visualization_data', {})
        if viz_data and viz_data.get('nodes') and viz_data.get('edges'):
            chart_data = {
                "nodes": viz_data['nodes'],
                "edges": viz_data['edges'],
                "type": "network"
            }
            
            config = {
                "layout": "force",
                "node_size_field": "message_count",
                "edge_width_field": "weight",
                "show_labels": True
            }
            
            charts.append(self.standardizer.create_chart_config(
                "network", "社交网络图", chart_data, config
            ))
        
        # 2. 中心性指标柱状图
        centrality_metrics = result.get('centrality_metrics', {})
        if centrality_metrics:
            degree_centrality = centrality_metrics.get('degree_centrality', {})
            
            if degree_centrality:
                sorted_centrality = sorted(degree_centrality.items(), 
                                         key=lambda x: x[1], reverse=True)[:10]
                
                chart_data = {
                    "labels": [user for user, _ in sorted_centrality],
                    "values": [centrality for _, centrality in sorted_centrality],
                    "type": "bar"
                }
                
                config = {
                    "xaxis": {"title": "用户"},
                    "yaxis": {"title": "度中心性"},
                    "orientation": "horizontal"
                }
                
                charts.append(self.standardizer.create_chart_config(
                    "bar", "用户影响力排名", chart_data, config
                ))
        
        return charts
    
    def _aggregate_sentiment_by_time(self, detailed_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """按时间聚合情感数据"""
        time_sentiment = {}
        
        try:
            for item in detailed_results:
                time_str = item.get('time', '')
                score = item.get('score', 0)
                
                if time_str:
                    # 提取日期部分
                    date_part = time_str.split('T')[0] if 'T' in time_str else time_str[:10]
                    
                    if date_part not in time_sentiment:
                        time_sentiment[date_part] = []
                    
                    time_sentiment[date_part].append(score)
            
            # 计算每天的平均情感分数
            for date, scores in time_sentiment.items():
                time_sentiment[date] = sum(scores) / len(scores) if scores else 0
            
        except Exception as e:
            logger.error(f"聚合情感时间数据失败: {e}")
        
        return time_sentiment
    
    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        return {
            'service_name': 'VisualizationService',
            'supported_chart_types': ['bar', 'line', 'pie', 'scatter', 'network', 'wordcloud'],
            'chart_version': '1.0'
        }


# 全局可视化服务实例
visualization_service = VisualizationService()


def get_visualization_service() -> VisualizationService:
    """获取可视化服务实例"""
    return visualization_service
