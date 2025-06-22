"""
情感分析器
分析聊天记录的情感倾向
使用 Transformers 深度学习模型进行高精度情感分析
"""

import re
from typing import Dict, List, Any, Optional
from .base import BaseAnalyzer
import logging

# 进度显示
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

logger = logging.getLogger(__name__)

# 导入 Transformers 依赖
from transformers import pipeline
import torch


class SentimentAnalyzer(BaseAnalyzer):
    """情感分析器 - 使用 Transformers 深度学习模型"""

    def __init__(self, show_progress: bool = True):
        """
        初始化情感分析器

        Args:
            show_progress: 是否显示分析进度
        """
        super().__init__(
            name="情感分析器",
            description="分析聊天记录的情感倾向，使用Transformers深度学习模型"
        )

        self.model_type = "transformers"
        self.show_progress = show_progress
        self.pipeline = None



        # 情感标签映射 - 支持IDEA-CCNL/Erlangshen-Roberta-110M-Sentiment模型
        self.emotion_labels = {
            'POSITIVE': 'positive', 'NEGATIVE': 'negative', 'NEUTRAL': 'neutral',
            'Positive': 'positive', 'Negative': 'negative', 'Neutral': 'neutral',
            'LABEL_0': 'negative', 'LABEL_1': 'positive', 'LABEL_2': 'neutral'
        }

        # 初始化模型
        self._initialize_model()

    def _initialize_model(self):
        """初始化Transformers情感分析模型"""
        logger.info("初始化Transformers深度学习模型")
        self._initialize_transformers_model()

    def _initialize_transformers_model(self):
        """初始化Transformers模型"""
        try:
            # 使用模型管理器获取单例模型
            from core.model_manager import get_model_manager
            model_manager = get_model_manager()

            self.pipeline = model_manager.get_sentiment_model()

            if self.pipeline:
                logger.info("Transformers模型初始化成功（使用模型管理器）")
            else:
                logger.error("模型管理器返回空模型")

        except Exception as e:
            logger.error(f"Transformers模型初始化失败: {e}")
            self.pipeline = None

    def _preprocess_text(self, text: str) -> str:
        """预处理文本，保留表情符号并限制长度"""
        # 保留中文、英文、数字、常见标点和表情符号
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # 限制文本长度，避免超过模型的最大输入长度
        # 中文字符大约1个字符=1个token，为了安全起见，限制为400个字符
        if len(text) > 400:
            text = text[:350] + "..."

        return text

    def _analyze_with_transformers(self, text: str) -> Dict[str, Any]:
        """使用深度学习模型分析情感"""
        try:
            text = self._preprocess_text(text)
            if not text.strip():
                return {'sentiment': 'neutral', 'confidence': 0.0, 'method': 'transformers'}

            results = self.pipeline(text)

            if isinstance(results, list) and len(results) > 0:
                if isinstance(results[0], list):
                    scores = {item['label']: item['score'] for item in results[0]}
                else:
                    scores = {results[0]['label']: results[0]['score']}

                best_label = max(scores.keys(), key=lambda k: scores[k])
                best_score = scores[best_label]

                sentiment = self.emotion_labels.get(best_label, best_label).lower()

                # 计算分数（保持向后兼容）
                if sentiment == 'positive':
                    score = best_score
                elif sentiment == 'negative':
                    score = -best_score
                else:
                    score = 0.0

                return {
                    'sentiment': sentiment,
                    'confidence': best_score,
                    'score': score,
                    'scores': scores,
                    'method': 'transformers'
                }

        except Exception as e:
            logger.error(f"深度学习分析失败: {e}")

        return {'sentiment': 'neutral', 'confidence': 0.0, 'method': 'transformers_failed'}

    def _update_task_progress(self, task_id: str, progress: float, message: str):
        """更新任务进度"""
        try:
            from core.task_queue import get_task_queue
            task_queue = get_task_queue()
            task_queue.update_task_progress(task_id, progress, message)
        except Exception as e:
            logger.warning(f"更新进度失败: {e}")

    def analyze_single_text(self, text: str) -> Dict[str, Any]:
        """分析单条文本的情感"""
        return self._analyze_with_transformers(text)

    def analyze(self, data: List[Dict], task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行增强版情感分析

        Args:
            data: 聊天记录数据列表

        Returns:
            分析结果字典
        """
        logger.info(f"开始情感分析，使用方法: {self.model_type}")

        sentiment_results = []
        positive_messages = []
        negative_messages = []
        neutral_messages = []
        confidences = []

        # 创建进度显示
        if self.show_progress and TQDM_AVAILABLE:
            data_iter = tqdm(data, desc="情感分析进度", unit="条消息")
            use_tqdm = True
        else:
            data_iter = data
            use_tqdm = False
            if self.show_progress:
                logger.info(f"开始分析 {len(data)} 条消息...")

        # 用于进度显示和 WebSocket 更新
        total_count = len(data)
        processed_count = 0
        last_logged_percent = -1
        last_websocket_percent = -1

        for item in data_iter:
            content = item.get('content', '')
            if not content:
                continue

            # 使用增强的分析方法
            result = self.analyze_single_text(content)
            sentiment = result.get('sentiment', 'neutral')
            confidence = result.get('confidence', 0.0)

            # 计算兼容的分数（保持向后兼容）
            if sentiment == 'positive':
                score = confidence
            elif sentiment == 'negative':
                score = -confidence
            else:
                score = 0.0

            sentiment_results.append({
                'content': content,
                'sentiment': sentiment,
                'confidence': confidence,
                'score': score,
                'time': item.get('time', ''),
                'method': result.get('method', self.model_type)
            })

            confidences.append(confidence)

            # 分类消息
            message_data = {
                'content': content,
                'score': score,
                'confidence': confidence,
                'time': item.get('time', '')
            }

            if sentiment == 'positive':
                positive_messages.append(message_data)
            elif sentiment == 'negative':
                negative_messages.append(message_data)
            else:
                neutral_messages.append(message_data)

            # 更新进度（统一处理 tqdm 和非 tqdm 情况的 WebSocket 更新）
            if self.show_progress:
                processed_count += 1
                current_percent = int((processed_count / total_count) * 100)

                # WebSocket 进度更新（每5%更新一次，减少频率）
                if task_id and current_percent > last_websocket_percent and current_percent % 5 == 0:
                    self._update_task_progress(task_id, current_percent, f"情感分析进度: {processed_count}/{total_count}")
                    last_websocket_percent = current_percent

                # 日志进度显示（仅在没有 tqdm 时）
                if not TQDM_AVAILABLE and current_percent > last_logged_percent and current_percent % 10 == 0:
                    logger.info(f"分析进度: {current_percent}% ({processed_count}/{total_count})")
                    last_logged_percent = current_percent

        # 统计结果
        total_messages = len(sentiment_results)
        if total_messages == 0:
            return {
                'total_messages': 0,
                'average_sentiment': 0,
                'average_confidence': 0,
                'sentiment_distribution': {'positive': 0, 'neutral': 0, 'negative': 0},
                'positive_messages': [],
                'negative_messages': [],
                'neutral_messages': [],
                'model_info': {'type': self.model_type, 'available': True}
            }

        # 计算平均值
        scores = [r['score'] for r in sentiment_results]
        average_sentiment = sum(scores) / total_messages
        average_confidence = sum(confidences) / total_messages

        # 情感分布
        sentiment_distribution = {
            'positive': len(positive_messages),
            'neutral': len(neutral_messages),
            'negative': len(negative_messages)
        }

        # 找出最积极和最消极的消息（按置信度排序）
        top_positive = sorted(positive_messages, key=lambda x: x['confidence'], reverse=True)[:5]
        top_negative = sorted(negative_messages, key=lambda x: x['confidence'], reverse=True)[:5]

        # 情感趋势分析
        sentiment_trend = self._analyze_sentiment_trend_enhanced(sentiment_results)

        results = {
            'total_messages': total_messages,
            'average_sentiment': average_sentiment,
            'average_confidence': average_confidence,
            'sentiment_distribution': sentiment_distribution,
            'sentiment_percentage': {
                'positive': len(positive_messages) / total_messages * 100,
                'neutral': len(neutral_messages) / total_messages * 100,
                'negative': len(negative_messages) / total_messages * 100
            },
            'top_positive_messages': top_positive,
            'top_negative_messages': top_negative,
            'sentiment_trend': sentiment_trend,
            'model_info': {
                'type': self.model_type,
                'model_name': 'IDEA-CCNL/Erlangshen-Roberta-110M-Sentiment'
            },
            'detailed_results': sentiment_results  # 保存详细结果用于证据展示
        }

        logger.info(f"情感分析完成，共分析 {total_messages} 条消息，平均置信度: {average_confidence:.3f}")

        # 自动生成图表数据
        try:
            chart_data = self._generate_chart_data(results)
            results['chart_data'] = chart_data
            logger.info("图表数据生成完成")
        except Exception as e:
            logger.warning(f"图表数据生成失败: {e}")

        return results
    


    def _analyze_sentiment_trend_enhanced(self, results: List[Dict]) -> Dict[str, Any]:
        """分析增强版情感趋势"""
        if len(results) < 2:
            return {'trend': 'stable', 'change_rate': 0, 'confidence_trend': 'stable'}

        scores = [r['score'] for r in results]
        confidences = [r['confidence'] for r in results]

        mid_point = len(scores) // 2
        first_half_avg = sum(scores[:mid_point]) / mid_point
        second_half_avg = sum(scores[mid_point:]) / (len(scores) - mid_point)

        first_half_conf = sum(confidences[:mid_point]) / mid_point
        second_half_conf = sum(confidences[mid_point:]) / (len(confidences) - mid_point)

        change_rate = second_half_avg - first_half_avg
        conf_change = second_half_conf - first_half_conf

        if change_rate > 0.1:
            trend = 'improving'
        elif change_rate < -0.1:
            trend = 'declining'
        else:
            trend = 'stable'

        if conf_change > 0.05:
            confidence_trend = 'increasing'
        elif conf_change < -0.05:
            confidence_trend = 'decreasing'
        else:
            confidence_trend = 'stable'

        return {
            'trend': trend,
            'change_rate': change_rate,
            'confidence_trend': confidence_trend,
            'confidence_change': conf_change,
            'first_half_avg': first_half_avg,
            'second_half_avg': second_half_avg,
            'first_half_confidence': first_half_conf,
            'second_half_confidence': second_half_conf
        }


    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取分析摘要
        
        Returns:
            分析摘要字典
        """
        if not self.is_analyzed:
            return {}
        
        results = self.results
        sentiment_percent = results.get('sentiment_percentage', {})
        model_info = results.get('model_info', {})

        # 确定主要情感
        if sentiment_percent.get('positive', 0) > sentiment_percent.get('negative', 0):
            main_sentiment = '积极'
        elif sentiment_percent.get('negative', 0) > sentiment_percent.get('positive', 0):
            main_sentiment = '消极'
        else:
            main_sentiment = '中性'

        # 基础摘要
        summary = {
            '总消息数': results.get('total_messages', 0),
            '平均情感分数': f"{results.get('average_sentiment', 0):.3f}",
            '主要情感倾向': main_sentiment,
            '积极消息比例': f"{sentiment_percent.get('positive', 0):.1f}%",
            '消极消息比例': f"{sentiment_percent.get('negative', 0):.1f}%",
            '中性消息比例': f"{sentiment_percent.get('neutral', 0):.1f}%",
            '情感趋势': results.get('sentiment_trend', {}).get('trend', '未知'),
            '分析方法': model_info.get('type', '词典')
        }

        # 如果有置信度信息，添加到摘要中
        if 'average_confidence' in results:
            summary['平均置信度'] = f"{results.get('average_confidence', 0):.3f}"

        # 添加详细证据信息
        detailed_results = results.get('detailed_results', [])
        if detailed_results:
            # 置信度分布
            high_conf = sum(1 for r in detailed_results if r['confidence'] > 0.8)
            med_conf = sum(1 for r in detailed_results if 0.5 <= r['confidence'] <= 0.8)
            low_conf = sum(1 for r in detailed_results if r['confidence'] < 0.5)
            total = len(detailed_results)

            summary.update({
                '高置信度分析': f"{high_conf}条 ({high_conf/total*100:.1f}%)",
                '中等置信度分析': f"{med_conf}条 ({med_conf/total*100:.1f}%)",
                '低置信度分析': f"{low_conf}条 ({low_conf/total*100:.1f}%)"
            })

            # 最确信的示例（前3个）
            positive_examples = sorted(
                [r for r in detailed_results if r['sentiment'] == 'positive'],
                key=lambda x: x['confidence'], reverse=True
            )[:3]

            negative_examples = sorted(
                [r for r in detailed_results if r['sentiment'] == 'negative'],
                key=lambda x: x['confidence'], reverse=True
            )[:3]

            if positive_examples:
                summary['最确信积极示例'] = [
                    f"[{ex['confidence']:.3f}] {ex['content'][:50]}..."
                    if len(ex['content']) > 50 else f"[{ex['confidence']:.3f}] {ex['content']}"
                    for ex in positive_examples
                ]

            if negative_examples:
                summary['最确信消极示例'] = [
                    f"[{ex['confidence']:.3f}] {ex['content'][:50]}..."
                    if len(ex['content']) > 50 else f"[{ex['confidence']:.3f}] {ex['content']}"
                    for ex in negative_examples
                ]



        return summary

    def get_detailed_evidence(self, top_n: int = 10) -> Dict[str, Any]:
        """
        获取详细的分析证据和示例

        Args:
            top_n: 每个类别显示的示例数量

        Returns:
            包含详细证据的字典
        """
        if not self.is_analyzed:
            return {}

        results = self.results
        detailed_results = results.get('detailed_results', [])

        if not detailed_results:
            return {}

        # 按情感分类并按置信度排序
        positive_examples = sorted(
            [r for r in detailed_results if r['sentiment'] == 'positive'],
            key=lambda x: x['confidence'], reverse=True
        )[:top_n]

        negative_examples = sorted(
            [r for r in detailed_results if r['sentiment'] == 'negative'],
            key=lambda x: x['confidence'], reverse=True
        )[:top_n]

        neutral_examples = sorted(
            [r for r in detailed_results if r['sentiment'] == 'neutral'],
            key=lambda x: x['confidence'], reverse=True
        )[:top_n]

        # 统计置信度分布
        confidence_ranges = {
            '高置信度 (>0.8)': 0,
            '中等置信度 (0.5-0.8)': 0,
            '低置信度 (<0.5)': 0
        }

        for result in detailed_results:
            conf = result['confidence']
            if conf > 0.8:
                confidence_ranges['高置信度 (>0.8)'] += 1
            elif conf > 0.5:
                confidence_ranges['中等置信度 (0.5-0.8)'] += 1
            else:
                confidence_ranges['低置信度 (<0.5)'] += 1



        return {
            'positive_examples': [
                {
                    'content': ex['content'],
                    'confidence': f"{ex['confidence']:.3f}",
                    'time': ex.get('time', ''),
                    'method': ex.get('method', '')
                } for ex in positive_examples
            ],
            'negative_examples': [
                {
                    'content': ex['content'],
                    'confidence': f"{ex['confidence']:.3f}",
                    'time': ex.get('time', ''),
                    'method': ex.get('method', '')
                } for ex in negative_examples
            ],
            'neutral_examples': [
                {
                    'content': ex['content'],
                    'confidence': f"{ex['confidence']:.3f}",
                    'time': ex.get('time', ''),
                    'method': ex.get('method', '')
                } for ex in neutral_examples
            ],
            'confidence_distribution': confidence_ranges,
            'analysis_summary': {
                'total_analyzed': len(detailed_results),
                'avg_confidence': f"{sum(r['confidence'] for r in detailed_results) / len(detailed_results):.3f}",
                'method_used': results.get('model_info', {}).get('type', 'unknown')
            }
        }

    def _generate_chart_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成情感分析图表数据

        Args:
            results: 分析结果字典

        Returns:
            图表数据字典
        """
        detailed_results = results.get('detailed_results', [])

        if not detailed_results:
            return {}

        # 时间序列数据（如果有时间信息）
        time_series = []
        sentiment_over_time = []
        confidence_over_time = []

        for i, result in enumerate(detailed_results):
            time_series.append(i + 1)  # 消息序号

            # 将情感转换为数值
            if result['sentiment'] == 'positive':
                sentiment_value = result['confidence']
            elif result['sentiment'] == 'negative':
                sentiment_value = -result['confidence']
            else:
                sentiment_value = 0

            sentiment_over_time.append(sentiment_value)
            confidence_over_time.append(result['confidence'])

        # 情感分布饼图数据
        sentiment_dist = results.get('sentiment_distribution', {})
        pie_data = {
            'labels': ['积极', '中性', '消极'],
            'values': [
                sentiment_dist.get('positive', 0),
                sentiment_dist.get('neutral', 0),
                sentiment_dist.get('negative', 0)
            ],
            'colors': ['#4CAF50', '#FFC107', '#F44336']
        }

        # 置信度分布直方图数据
        confidence_bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        confidence_counts = [0] * (len(confidence_bins) - 1)

        for result in detailed_results:
            conf = result['confidence']
            for i in range(len(confidence_bins) - 1):
                if confidence_bins[i] <= conf < confidence_bins[i + 1]:
                    confidence_counts[i] += 1
                    break
            else:
                if conf == 1.0:
                    confidence_counts[-1] += 1

        return {
            'time_series': {
                'x': time_series,
                'sentiment': sentiment_over_time,
                'confidence': confidence_over_time
            },
            'sentiment_pie': pie_data,
            'confidence_histogram': {
                'bins': ['0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0'],
                'counts': confidence_counts
            },
            'summary_stats': {
                'total_messages': len(detailed_results),
                'avg_sentiment': f"{results.get('average_sentiment', 0):.3f}",
                'avg_confidence': f"{results.get('average_confidence', 0):.3f}",
                'sentiment_range': {
                    'min': min(sentiment_over_time),
                    'max': max(sentiment_over_time)
                }
            }
        }

    def generate_sentiment_chart_data(self) -> Dict[str, Any]:
        """
        获取情感分析图表数据（向后兼容方法）

        Returns:
            图表数据字典
        """
        if not self.is_analyzed:
            return {}

        return self._generate_chart_data(self.results)