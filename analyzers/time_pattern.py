"""
时间模式分析器
分析聊天记录的时间分布和活跃模式
"""

from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple, Optional
from .base import BaseAnalyzer
import logging
import pandas as pd
import numpy as np
from scipy import stats
import pytz

try:
    from statsmodels.tsa.seasonal import seasonal_decompose
    from statsmodels.stats.diagnostic import acorr_ljungbox
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logging.warning("statsmodels未安装，部分高级时间序列分析功能将不可用")

logger = logging.getLogger(__name__)


class TimePatternAnalyzer(BaseAnalyzer):
    """时间模式分析器"""
    
    def __init__(self):
        """初始化时间模式分析器"""
        super().__init__(
            name="时间模式分析器",
            description="分析聊天记录的时间分布和活跃模式"
        )
    
    def analyze(self, data: List[Dict], task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行时间模式分析

        Args:
            data: 聊天记录数据列表

        Returns:
            分析结果字典
        """
        logger.info("开始时间模式分析")

        # 解析时间数据
        time_data = self._parse_time_data(data)

        if not time_data:
            logger.warning("没有有效的时间数据")
            return {'error': '没有有效的时间数据'}

        # 创建pandas DataFrame用于高级分析
        df = self._create_dataframe(time_data)

        # 基础统计分析
        hourly_stats = self._analyze_hourly_pattern(time_data)
        weekly_stats = self._analyze_weekly_pattern(time_data)
        daily_stats = self._analyze_daily_pattern(time_data)
        active_periods = self._analyze_active_periods(time_data)
        interval_stats = self._analyze_message_intervals(time_data)

        # 高级分析
        trend_analysis = self._analyze_trends(df)
        periodicity_analysis = self._analyze_periodicity(df)
        activity_intensity = self._analyze_activity_intensity(df)
        anomaly_detection = self._detect_anomalies(df)
        statistical_analysis = self._statistical_analysis(time_data)

        # 分钟级分析
        minute_analysis = self._analyze_minute_patterns(time_data)

        results = {
            'total_messages': len(time_data),
            'time_span': {
                'start': time_data[0]['datetime'].isoformat() if time_data else None,
                'end': time_data[-1]['datetime'].isoformat() if time_data else None,
                'duration_days': (time_data[-1]['datetime'] - time_data[0]['datetime']).days if len(time_data) > 1 else 0
            },
            'hourly_distribution': hourly_stats,
            'weekly_distribution': weekly_stats,
            'daily_distribution': daily_stats,
            'active_periods': active_periods,
            'interval_stats': interval_stats,
            'peak_hours': self._find_peak_hours(hourly_stats),
            'peak_days': self._find_peak_days(weekly_stats),

            # 新增高级分析结果
            'trend_analysis': trend_analysis,
            'periodicity_analysis': periodicity_analysis,
            'activity_intensity': activity_intensity,
            'anomaly_detection': anomaly_detection,
            'statistical_analysis': statistical_analysis,
            'minute_analysis': minute_analysis
        }

        logger.info(f"时间模式分析完成，共分析 {len(time_data)} 条消息")
        return results
    
    def _parse_time_data(self, data: List[Dict]) -> List[Dict]:
        """
        解析时间数据
        
        Args:
            data: 原始数据
            
        Returns:
            包含时间信息的处理后的数据
        """
        time_data = []
        
        for item in data:
            time_str = item.get('time', '')
            if time_str:
                try:
                    # 解析ISO格式时间
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    time_data.append({
                        'datetime': dt,
                        'hour': dt.hour,
                        'weekday': dt.weekday(),
                        'date': dt.date(),
                        'content': item.get('content', ''),
                        'is_self': item.get('isSelf', False)
                    })
                except ValueError as e:
                    logger.warning(f"时间解析失败: {time_str}, 错误: {e}")
                    continue
        
        # 按时间排序
        time_data.sort(key=lambda x: x['datetime'])
        return time_data

    def _create_dataframe(self, time_data: List[Dict]) -> pd.DataFrame:
        """
        创建pandas DataFrame用于高级分析

        Args:
            time_data: 时间数据

        Returns:
            pandas DataFrame
        """
        if not time_data:
            return pd.DataFrame()

        # 创建DataFrame
        df = pd.DataFrame(time_data)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)

        # 添加更多时间特征
        df['minute'] = df.index.minute
        df['day_of_year'] = df.index.dayofyear
        df['week_of_year'] = df.index.isocalendar().week
        df['month'] = df.index.month
        df['quarter'] = df.index.quarter
        df['is_weekend'] = df.index.weekday >= 5

        # 创建消息计数时间序列（按小时重采样）
        hourly_counts = df.resample('H').size()
        df_hourly = pd.DataFrame({'message_count': hourly_counts})
        df_hourly['hour'] = df_hourly.index.hour
        df_hourly['weekday'] = df_hourly.index.weekday
        df_hourly['date'] = df_hourly.index.date

        return df_hourly

    def _analyze_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析时间趋势

        Args:
            df: 时间数据DataFrame

        Returns:
            趋势分析结果
        """
        if df.empty or len(df) < 7:
            return {'trend': 'insufficient_data', 'slope': 0, 'correlation': 0}

        try:
            # 计算每日消息总数
            daily_counts = df.groupby('date')['message_count'].sum()

            if len(daily_counts) < 3:
                return {'trend': 'insufficient_data', 'slope': 0, 'correlation': 0}

            # 线性回归分析趋势
            x = np.arange(len(daily_counts))
            y = daily_counts.values

            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

            # 判断趋势方向
            if abs(slope) < 0.1:
                trend = 'stable'
            elif slope > 0:
                trend = 'increasing'
            else:
                trend = 'decreasing'

            # 计算变化率
            if len(daily_counts) > 1:
                change_rate = (daily_counts.iloc[-1] - daily_counts.iloc[0]) / daily_counts.iloc[0] * 100
            else:
                change_rate = 0

            return {
                'trend': trend,
                'slope': float(slope),
                'correlation': float(r_value),
                'p_value': float(p_value),
                'change_rate_percent': float(change_rate),
                'daily_average': float(daily_counts.mean()),
                'daily_std': float(daily_counts.std())
            }
        except Exception as e:
            logger.warning(f"趋势分析失败: {e}")
            return {'trend': 'analysis_failed', 'slope': 0, 'correlation': 0}

    def _analyze_periodicity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析周期性模式

        Args:
            df: 时间数据DataFrame

        Returns:
            周期性分析结果
        """
        if df.empty or len(df) < 14:  # 至少需要两周数据
            return {'has_weekly_pattern': False, 'has_daily_pattern': False}

        try:
            # 按小时分组分析日内周期性
            hourly_pattern = df.groupby('hour')['message_count'].mean()
            daily_variation = hourly_pattern.std() / hourly_pattern.mean() if hourly_pattern.mean() > 0 else 0

            # 按星期分组分析周内周期性
            weekly_pattern = df.groupby('weekday')['message_count'].mean()
            weekly_variation = weekly_pattern.std() / weekly_pattern.mean() if weekly_pattern.mean() > 0 else 0

            # 使用统计检验判断是否存在显著的周期性
            # Kruskal-Wallis检验（非参数检验）
            hourly_groups = [df[df['hour'] == h]['message_count'].values for h in range(24)]
            hourly_groups = [g for g in hourly_groups if len(g) > 0]

            weekly_groups = [df[df['weekday'] == d]['message_count'].values for d in range(7)]
            weekly_groups = [g for g in weekly_groups if len(g) > 0]

            has_daily_pattern = False
            has_weekly_pattern = False
            daily_p_value = 1.0
            weekly_p_value = 1.0

            if len(hourly_groups) >= 3:
                try:
                    daily_stat, daily_p_value = stats.kruskal(*hourly_groups)
                    has_daily_pattern = daily_p_value < 0.05 and daily_variation > 0.3
                except:
                    pass

            if len(weekly_groups) >= 3:
                try:
                    weekly_stat, weekly_p_value = stats.kruskal(*weekly_groups)
                    has_weekly_pattern = weekly_p_value < 0.05 and weekly_variation > 0.2
                except:
                    pass

            # 时间序列分解（如果statsmodels可用）
            decomposition_result = None
            if STATSMODELS_AVAILABLE and len(df) >= 48:  # 至少48小时数据
                try:
                    # 重采样为每小时数据并填充缺失值
                    ts = df['message_count'].resample('H').sum().fillna(0)
                    if len(ts) >= 48:
                        decomposition = seasonal_decompose(ts, model='additive', period=24)
                        decomposition_result = {
                            'seasonal_strength': float(np.var(decomposition.seasonal) / np.var(ts)),
                            'trend_strength': float(np.var(decomposition.trend.dropna()) / np.var(ts)),
                            'residual_strength': float(np.var(decomposition.resid.dropna()) / np.var(ts))
                        }
                except Exception as e:
                    logger.warning(f"时间序列分解失败: {e}")

            return {
                'has_daily_pattern': has_daily_pattern,
                'has_weekly_pattern': has_weekly_pattern,
                'daily_variation_coefficient': float(daily_variation),
                'weekly_variation_coefficient': float(weekly_variation),
                'daily_pattern_p_value': float(daily_p_value),
                'weekly_pattern_p_value': float(weekly_p_value),
                'hourly_peak_hours': hourly_pattern.nlargest(3).index.tolist(),
                'weekly_peak_days': weekly_pattern.nlargest(3).index.tolist(),
                'decomposition': decomposition_result
            }
        except Exception as e:
            logger.warning(f"周期性分析失败: {e}")
            return {'has_weekly_pattern': False, 'has_daily_pattern': False}

    def _analyze_activity_intensity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析活动强度

        Args:
            df: 时间数据DataFrame

        Returns:
            活动强度分析结果
        """
        if df.empty:
            return {'intensity_level': 'no_data'}

        try:
            # 计算每小时平均消息数
            hourly_avg = df['message_count'].mean()
            hourly_std = df['message_count'].std()

            # 计算活动强度等级
            if hourly_avg < 1:
                intensity_level = 'low'
            elif hourly_avg < 5:
                intensity_level = 'medium'
            elif hourly_avg < 15:
                intensity_level = 'high'
            else:
                intensity_level = 'very_high'

            # 计算活动集中度（基尼系数）
            message_counts = df['message_count'].values
            message_counts = message_counts[message_counts > 0]  # 只考虑有消息的时段

            if len(message_counts) > 1:
                # 计算基尼系数
                sorted_counts = np.sort(message_counts)
                n = len(sorted_counts)
                cumsum = np.cumsum(sorted_counts)
                gini = (2 * np.sum((np.arange(1, n + 1) * sorted_counts))) / (n * cumsum[-1]) - (n + 1) / n
            else:
                gini = 0

            # 活跃时段比例
            active_hours = len(df[df['message_count'] > 0])
            total_hours = len(df)
            activity_ratio = active_hours / total_hours if total_hours > 0 else 0

            # 突发活动检测（消息数超过平均值+2倍标准差的时段）
            threshold = hourly_avg + 2 * hourly_std
            burst_periods = df[df['message_count'] > threshold]

            return {
                'intensity_level': intensity_level,
                'hourly_average': float(hourly_avg),
                'hourly_std': float(hourly_std),
                'activity_concentration_gini': float(gini),
                'activity_ratio': float(activity_ratio),
                'burst_periods_count': len(burst_periods),
                'max_hourly_messages': int(df['message_count'].max()),
                'min_hourly_messages': int(df['message_count'].min()),
                'active_hours_total': int(active_hours)
            }
        except Exception as e:
            logger.warning(f"活动强度分析失败: {e}")
            return {'intensity_level': 'analysis_failed'}

    def _detect_anomalies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        检测异常活动模式

        Args:
            df: 时间数据DataFrame

        Returns:
            异常检测结果
        """
        if df.empty or len(df) < 24:
            return {'anomalies_detected': False, 'anomaly_count': 0}

        try:
            # 使用IQR方法检测异常值
            Q1 = df['message_count'].quantile(0.25)
            Q3 = df['message_count'].quantile(0.75)
            IQR = Q3 - Q1

            # 定义异常值边界
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            # 检测异常值
            anomalies = df[(df['message_count'] < lower_bound) | (df['message_count'] > upper_bound)]

            # 使用Z-score方法作为补充
            z_scores = np.abs(stats.zscore(df['message_count']))
            z_anomalies = df[z_scores > 2.5]  # Z-score > 2.5认为是异常

            # 检测连续异常活跃期
            consecutive_high = []
            high_threshold = df['message_count'].quantile(0.9)
            current_streak = 0

            for idx, count in enumerate(df['message_count']):
                if count > high_threshold:
                    current_streak += 1
                else:
                    if current_streak >= 3:  # 连续3小时以上高活跃
                        consecutive_high.append(current_streak)
                    current_streak = 0

            # 检测异常静默期
            consecutive_low = []
            low_threshold = df['message_count'].quantile(0.1)
            current_silence = 0

            for idx, count in enumerate(df['message_count']):
                if count <= low_threshold:
                    current_silence += 1
                else:
                    if current_silence >= 6:  # 连续6小时以上低活跃
                        consecutive_low.append(current_silence)
                    current_silence = 0

            return {
                'anomalies_detected': len(anomalies) > 0 or len(z_anomalies) > 0,
                'anomaly_count': len(anomalies),
                'z_score_anomaly_count': len(z_anomalies),
                'consecutive_high_periods': consecutive_high,
                'consecutive_low_periods': consecutive_low,
                'iqr_bounds': {'lower': float(lower_bound), 'upper': float(upper_bound)},
                'anomaly_timestamps': anomalies.index.strftime('%Y-%m-%d %H:%M').tolist() if len(anomalies) > 0 else []
            }
        except Exception as e:
            logger.warning(f"异常检测失败: {e}")
            return {'anomalies_detected': False, 'anomaly_count': 0}

    def _statistical_analysis(self, time_data: List[Dict]) -> Dict[str, Any]:
        """
        统计学分析

        Args:
            time_data: 时间数据

        Returns:
            统计分析结果
        """
        if not time_data:
            return {'distribution_type': 'no_data'}

        try:
            # 提取小时数据进行分布分析
            hours = [item['hour'] for item in time_data]
            hour_counts = Counter(hours)

            # 确保所有24小时都有数据，没有消息的小时计数为0
            hour_values = [hour_counts.get(h, 0) for h in range(24)]

            if sum(hour_values) < 3:
                return {'distribution_type': 'insufficient_data'}

            # 正态性检验
            shapiro_stat, shapiro_p = stats.shapiro(hour_values)
            is_normal = shapiro_p > 0.05

            # 计算偏度和峰度
            skewness = stats.skew(hour_values)
            kurtosis = stats.kurtosis(hour_values)

            # 均匀性检验（卡方检验）
            # 现在hour_values包含所有24小时的数据，期望频率也是24个
            expected_freq = len(time_data) / 24
            chi2_stat, chi2_p = stats.chisquare(hour_values, [expected_freq] * 24)
            is_uniform = chi2_p > 0.05

            # 计算熵（信息熵）
            total_messages = sum(hour_values)
            probabilities = [count / total_messages for count in hour_values if count > 0]
            entropy = -sum(p * np.log2(p) for p in probabilities)
            max_entropy = np.log2(24)  # 24小时的最大熵
            normalized_entropy = entropy / max_entropy

            # 集中度分析
            concentration_ratio = max(hour_values) / sum(hour_values) if sum(hour_values) > 0 else 0

            return {
                'distribution_type': 'normal' if is_normal else 'non_normal',
                'is_uniform': is_uniform,
                'shapiro_p_value': float(shapiro_p),
                'chi2_p_value': float(chi2_p),
                'skewness': float(skewness),
                'kurtosis': float(kurtosis),
                'entropy': float(entropy),
                'normalized_entropy': float(normalized_entropy),
                'concentration_ratio': float(concentration_ratio),
                'variance': float(np.var(hour_values)),
                'coefficient_of_variation': float(np.std(hour_values) / np.mean(hour_values)) if np.mean(hour_values) > 0 else 0
            }
        except Exception as e:
            logger.warning(f"统计分析失败: {e}")
            return {'distribution_type': 'analysis_failed'}

    def _analyze_minute_patterns(self, time_data: List[Dict]) -> Dict[str, Any]:
        """
        分析分钟级模式

        Args:
            time_data: 时间数据

        Returns:
            分钟级分析结果
        """
        if not time_data:
            return {'minute_distribution': {}}

        try:
            # 提取分钟数据
            minutes = [item['datetime'].minute for item in time_data]
            minute_counts = Counter(minutes)

            # 分析分钟分布模式
            # 检查是否有明显的分钟偏好（如整点、半点）
            round_minutes = [0, 15, 30, 45]  # 常见的"整"分钟
            round_minute_count = sum(minute_counts.get(m, 0) for m in round_minutes)
            total_count = len(time_data)
            round_minute_ratio = round_minute_count / total_count if total_count > 0 else 0

            # 计算分钟分布的均匀性
            minute_values = list(minute_counts.values())
            if len(minute_values) > 1:
                minute_cv = np.std(minute_values) / np.mean(minute_values)
            else:
                minute_cv = 0

            # 找出最常用的分钟
            top_minutes = minute_counts.most_common(5)

            return {
                'minute_distribution': dict(minute_counts),
                'round_minute_preference': round_minute_ratio > 0.3,
                'round_minute_ratio': float(round_minute_ratio),
                'minute_variation_coefficient': float(minute_cv),
                'top_minutes': top_minutes,
                'total_unique_minutes': len(minute_counts)
            }
        except Exception as e:
            logger.warning(f"分钟级分析失败: {e}")
            return {'minute_distribution': {}}
    
    def _analyze_hourly_pattern(self, time_data: List[Dict]) -> Dict[str, int]:
        """
        分析小时分布模式
        
        Args:
            time_data: 时间数据
            
        Returns:
            小时分布统计
        """
        hourly_counts = Counter()
        for item in time_data:
            hourly_counts[item['hour']] += 1
        
        return dict(hourly_counts)
    
    def _analyze_weekly_pattern(self, time_data: List[Dict]) -> Dict[str, int]:
        """
        分析星期分布模式
        
        Args:
            time_data: 时间数据
            
        Returns:
            星期分布统计
        """
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        weekly_counts = Counter()
        
        for item in time_data:
            weekday_name = weekday_names[item['weekday']]
            weekly_counts[weekday_name] += 1
        
        return dict(weekly_counts)
    
    def _analyze_daily_pattern(self, time_data: List[Dict]) -> Dict[str, int]:
        """
        分析日期分布模式
        
        Args:
            time_data: 时间数据
            
        Returns:
            日期分布统计
        """
        daily_counts = Counter()
        for item in time_data:
            date_str = item['date'].isoformat()
            daily_counts[date_str] += 1
        
        return dict(daily_counts)
    
    def _analyze_active_periods(self, time_data: List[Dict]) -> Dict[str, Any]:
        """
        分析活跃时间段
        
        Args:
            time_data: 时间数据
            
        Returns:
            活跃时间段分析结果
        """
        # 定义时间段
        periods = {
            '凌晨': (0, 6),
            '上午': (6, 12),
            '下午': (12, 18),
            '晚上': (18, 24)
        }
        
        period_counts = Counter()
        for item in time_data:
            hour = item['hour']
            for period_name, (start, end) in periods.items():
                if start <= hour < end:
                    period_counts[period_name] += 1
                    break
        
        # 找出最活跃的时间段
        most_active_period = period_counts.most_common(1)[0] if period_counts else None
        
        return {
            'period_distribution': dict(period_counts),
            'most_active_period': most_active_period
        }
    
    def _analyze_message_intervals(self, time_data: List[Dict]) -> Dict[str, Any]:
        """
        分析消息间隔
        
        Args:
            time_data: 时间数据
            
        Returns:
            消息间隔统计
        """
        if len(time_data) < 2:
            return {'average_interval': 0, 'min_interval': 0, 'max_interval': 0}
        
        intervals = []
        for i in range(1, len(time_data)):
            interval = (time_data[i]['datetime'] - time_data[i-1]['datetime']).total_seconds()
            intervals.append(interval)
        
        if not intervals:
            return {'average_interval': 0, 'min_interval': 0, 'max_interval': 0}
        
        return {
            'average_interval': sum(intervals) / len(intervals),
            'min_interval': min(intervals),
            'max_interval': max(intervals),
            'median_interval': sorted(intervals)[len(intervals)//2]
        }
    
    def _find_peak_hours(self, hourly_stats: Dict[str, int]) -> List[Tuple[int, int]]:
        """
        找出高峰时段
        
        Args:
            hourly_stats: 小时统计
            
        Returns:
            高峰时段列表
        """
        if not hourly_stats:
            return []
        
        # 找出前3个最活跃的小时
        sorted_hours = sorted(hourly_stats.items(), key=lambda x: x[1], reverse=True)
        return sorted_hours[:3]
    
    def _find_peak_days(self, weekly_stats: Dict[str, int]) -> List[Tuple[str, int]]:
        """
        找出高峰日期
        
        Args:
            weekly_stats: 星期统计
            
        Returns:
            高峰日期列表
        """
        if not weekly_stats:
            return []
        
        # 找出前3个最活跃的星期
        sorted_days = sorted(weekly_stats.items(), key=lambda x: x[1], reverse=True)
        return sorted_days[:3]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取分析摘要

        Returns:
            分析摘要字典
        """
        if not self.is_analyzed:
            return {}

        # 基础统计
        active_periods = self.results.get('active_periods', {})
        peak_hours = self.results.get('peak_hours', [])
        peak_days = self.results.get('peak_days', [])

        # 高级分析结果
        trend_analysis = self.results.get('trend_analysis', {})
        periodicity = self.results.get('periodicity_analysis', {})
        activity_intensity = self.results.get('activity_intensity', {})
        anomaly_detection = self.results.get('anomaly_detection', {})
        statistical_analysis = self.results.get('statistical_analysis', {})

        summary = {
            '总消息数': self.results.get('total_messages', 0),
            '时间跨度天数': self.results.get('time_span', {}).get('duration_days', 0),
            '最活跃时段': active_periods.get('most_active_period', ['无', 0])[0] if active_periods.get('most_active_period') else '无',
            '最活跃小时': f"{peak_hours[0][0]}时" if peak_hours else '无',
            '最活跃星期': peak_days[0][0] if peak_days else '无',
            '平均消息间隔': f"{self.results.get('interval_stats', {}).get('average_interval', 0):.1f}秒",

            # 趋势分析
            '活动趋势': trend_analysis.get('trend', '无数据'),
            '变化率': f"{trend_analysis.get('change_rate_percent', 0):.1f}%" if trend_analysis.get('change_rate_percent') else '无',

            # 周期性分析
            '存在日内周期性': '是' if periodicity.get('has_daily_pattern', False) else '否',
            '存在周内周期性': '是' if periodicity.get('has_weekly_pattern', False) else '否',

            # 活动强度
            '活动强度等级': activity_intensity.get('intensity_level', '无数据'),
            '每小时平均消息数': f"{activity_intensity.get('hourly_average', 0):.1f}",
            '活跃时段比例': f"{activity_intensity.get('activity_ratio', 0):.1%}",

            # 异常检测
            '检测到异常': '是' if anomaly_detection.get('anomalies_detected', False) else '否',
            '异常时段数量': anomaly_detection.get('anomaly_count', 0),

            # 统计特征
            '时间分布类型': statistical_analysis.get('distribution_type', '无数据'),
            '分布均匀性': '是' if statistical_analysis.get('is_uniform', False) else '否',
            '时间集中度': f"{statistical_analysis.get('concentration_ratio', 0):.3f}"
        }

        return summary