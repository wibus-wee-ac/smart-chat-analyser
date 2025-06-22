"""
高级社交网络分析器
使用NetworkX进行专业的社交网络分析，包括中心性、社区检测、关系强度等
针对中文聊天记录优化
"""

import networkx as nx
import community as community_louvain
import re
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple, Set
from datetime import datetime, timedelta
from .base import BaseAnalyzer
import logging

logger = logging.getLogger(__name__)


class SocialNetworkAnalyzer(BaseAnalyzer):
    """高级社交网络分析器 - 使用NetworkX进行专业图分析"""
    
    def __init__(self, time_window_minutes: int = 30, min_interaction_strength: float = 0.1):
        """
        初始化社交网络分析器
        
        Args:
            time_window_minutes: 互动时间窗口（分钟）
            min_interaction_strength: 最小互动强度阈值
        """
        super().__init__(
            name="社交网络分析器",
            description="使用NetworkX进行高级社交网络分析，包括中心性、社区检测、关系强度等"
        )
        self.name_cache = {}  # 缓存ID到名称的映射
        self.time_window = timedelta(minutes=time_window_minutes)
        self.min_interaction_strength = min_interaction_strength
        self.graph = nx.DiGraph()  # 有向图，表示互动方向
        self.undirected_graph = None  # 无向图，用于某些算法
    
    def _get_user_name(self, user_id: str) -> str:
        """获取用户名称"""
        if user_id in self.name_cache:
            return self.name_cache[user_id]
        return user_id
    
    def _cache_user_names(self, data: List[Dict]):
        """缓存用户名称"""
        for item in data:
            sender = item.get('sender', '')
            sender_name = item.get('senderName', '')
            talker = item.get('talker', '')
            talker_name = item.get('talkerName', '')
            is_self = item.get('isSelf', False)

            # 处理自己发送的消息
            if is_self:
                if sender == '__SELF__' or not sender:
                    self.name_cache['__SELF__'] = '我'
            elif sender and sender_name:
                self.name_cache[sender] = sender_name

            if talker and talker_name:
                self.name_cache[talker] = talker_name
    
    def _parse_time(self, time_str: str) -> datetime:
        """解析时间字符串"""
        try:
            # 尝试多种时间格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y/%m/%d %H:%M:%S',
                '%Y-%m-%d'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(time_str, fmt)
                except ValueError:
                    continue
            
            # 如果都失败，返回当前时间
            return datetime.now()
        except:
            return datetime.now()
    
    def _calculate_time_gap(self, time1: str, time2: str) -> timedelta:
        """计算时间间隔"""
        try:
            dt1 = self._parse_time(time1)
            dt2 = self._parse_time(time2)
            return abs(dt2 - dt1)
        except:
            return timedelta(hours=1)  # 默认1小时
    
    def _is_reply_interaction(self, content1: str, content2: str) -> bool:
        """判断是否为回复互动"""
        # 简单的回复检测逻辑
        reply_indicators = ['回复', '回答', '是的', '对的', '不是', '没有', '好的', '嗯', '哦', '啊']
        
        content2_lower = content2.lower()
        for indicator in reply_indicators:
            if indicator in content2_lower:
                return True
        
        # 检查是否包含问号后的回答
        if '?' in content1 or '？' in content1:
            return len(content2) > 0
        
        return False
    
    def _is_mention_interaction(self, content1: str, content2: str, sender1: str, sender2: str) -> bool:
        """判断是否为提及互动"""
        # 检查是否直接提及用户名
        sender1_name = self._get_user_name(sender1)
        sender2_name = self._get_user_name(sender2)
        
        if sender1_name in content2 or sender2_name in content1:
            return True
        
        # 检查@符号
        if '@' in content1 or '@' in content2:
            return True
        
        return False
    
    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """计算内容相似度"""
        if not content1 or not content2:
            return 0.0
        
        # 简单的词汇重叠相似度
        words1 = set(content1.split())
        words2 = set(content2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_interaction_strength(self, stats: Dict) -> float:
        """计算互动强度"""
        count = stats['count']
        reply_ratio = stats['reply_count'] / count if count > 0 else 0
        mention_ratio = stats['mention_count'] / count if count > 0 else 0
        avg_similarity = stats['content_similarity'] / count if count > 0 else 0
        
        # 综合计算强度
        strength = (
            count * 0.4 +  # 互动次数权重
            reply_ratio * 0.3 +  # 回复比例权重
            mention_ratio * 0.2 +  # 提及比例权重
            avg_similarity * 0.1  # 内容相似度权重
        )
        
        return min(strength, 1.0)  # 限制在0-1之间
    
    def _build_social_graph(self, data: List[Dict]):
        """构建社交网络图"""
        # 清空现有图
        self.graph.clear()
        
        # 按时间排序数据
        sorted_data = sorted(data, key=lambda x: x.get('time', ''))
        
        # 用户消息序列
        user_messages = defaultdict(list)
        
        for item in sorted_data:
            sender = item.get('sender', '')
            content = item.get('content', '')
            time_str = item.get('time', '')
            msg_type = item.get('type', 0)
            is_self = item.get('isSelf', False)

            # 处理自己发送的消息
            if is_self and not sender:
                sender = '__SELF__'

            if sender and content:
                user_messages[sender].append({
                    'time': time_str,
                    'content': content,
                    'type': msg_type
                })
        
        # 添加节点
        for user_id in user_messages.keys():
            user_name = self._get_user_name(user_id)
            message_count = len(user_messages[user_id])
            avg_length = sum(len(msg['content']) for msg in user_messages[user_id]) / message_count
            
            self.graph.add_node(user_id, 
                              name=user_name,
                              message_count=message_count,
                              avg_message_length=avg_length)
        
        # 分析互动关系并添加边
        self._add_interaction_edges(sorted_data)
        
        # 创建无向图用于某些算法
        self.undirected_graph = self.graph.to_undirected()
        
        logger.info(f"构建社交网络图完成：{self.graph.number_of_nodes()} 个节点，{self.graph.number_of_edges()} 条边")
    
    def _add_interaction_edges(self, data: List[Dict]):
        """添加互动关系边"""
        interactions = defaultdict(lambda: defaultdict(lambda: {
            'count': 0,
            'total_time_gap': 0,
            'reply_count': 0,
            'mention_count': 0,
            'content_similarity': 0
        }))
        
        for i in range(len(data)):
            current_msg = data[i]
            current_sender = current_msg.get('sender', '')
            current_content = current_msg.get('content', '')
            current_time = current_msg.get('time', '')
            current_is_self = current_msg.get('isSelf', False)

            # 处理自己发送的消息
            if current_is_self and not current_sender:
                current_sender = '__SELF__'

            if not current_sender:
                continue
            
            # 分析与后续消息的互动
            for j in range(i + 1, min(i + 10, len(data))):  # 检查后续10条消息
                next_msg = data[j]
                next_sender = next_msg.get('sender', '')
                next_content = next_msg.get('content', '')
                next_time = next_msg.get('time', '')
                next_is_self = next_msg.get('isSelf', False)

                # 处理自己发送的消息
                if next_is_self and not next_sender:
                    next_sender = '__SELF__'

                if not next_sender or current_sender == next_sender:
                    continue
                
                # 计算时间间隔
                time_gap = self._calculate_time_gap(current_time, next_time)
                if time_gap > self.time_window:
                    break  # 超出时间窗口
                
                # 检查是否为回复
                is_reply = self._is_reply_interaction(current_content, next_content)
                
                # 检查是否有提及
                is_mention = self._is_mention_interaction(current_content, next_content, current_sender, next_sender)
                
                # 计算内容相似度
                similarity = self._calculate_content_similarity(current_content, next_content)
                
                # 更新互动统计
                interaction = interactions[current_sender][next_sender]
                interaction['count'] += 1
                interaction['total_time_gap'] += time_gap.total_seconds()
                if is_reply:
                    interaction['reply_count'] += 1
                if is_mention:
                    interaction['mention_count'] += 1
                interaction['content_similarity'] += similarity
        
        # 添加边到图中
        for sender, receivers in interactions.items():
            for receiver, stats in receivers.items():
                if stats['count'] > 0:
                    # 计算互动强度
                    strength = self._calculate_interaction_strength(stats)
                    
                    if strength >= self.min_interaction_strength:
                        avg_time_gap = stats['total_time_gap'] / stats['count']
                        avg_similarity = stats['content_similarity'] / stats['count']
                        
                        self.graph.add_edge(sender, receiver,
                                          weight=strength,
                                          interaction_count=stats['count'],
                                          reply_count=stats['reply_count'],
                                          mention_count=stats['mention_count'],
                                          avg_time_gap=avg_time_gap,
                                          avg_similarity=avg_similarity)

    def analyze(self, data: List[Dict]) -> Dict[str, Any]:
        """执行高级社交网络分析"""
        logger.info("开始高级社交网络分析")

        # 缓存用户名称
        self._cache_user_names(data)

        # 构建社交网络图
        self._build_social_graph(data)

        # 分析用户活跃度
        user_activity = self._analyze_user_activity(data)

        # 计算网络中心性指标
        centrality_metrics = self._calculate_centrality_metrics()

        # 社区检测
        communities = self._detect_communities()

        # 分析互动强度和模式
        interaction_analysis = self._analyze_interaction_patterns()

        # 识别关键节点和影响者
        key_players = self._identify_key_players()

        # 分析网络结构特征
        network_structure = self._analyze_network_structure()

        # 生成可视化数据
        visualization_data = self._generate_visualization_data()

        results = {
            'total_messages': len(data),
            'total_users': self.graph.number_of_nodes(),
            'total_interactions': self.graph.number_of_edges(),
            'user_activity': user_activity,
            'centrality_metrics': centrality_metrics,
            'communities': communities,
            'interaction_analysis': interaction_analysis,
            'key_players': key_players,
            'network_structure': network_structure,
            'visualization_data': visualization_data
        }

        logger.info(f"社交网络分析完成，共分析 {len(data)} 条消息，{self.graph.number_of_nodes()} 个用户，{self.graph.number_of_edges()} 个互动关系")
        return results

    def _analyze_user_activity(self, data: List[Dict]) -> Dict[str, Any]:
        """分析用户活跃度"""
        user_stats = {}

        for node in self.graph.nodes():
            node_data = self.graph.nodes[node]
            user_stats[node] = {
                'message_count': node_data.get('message_count', 0),
                'avg_message_length': node_data.get('avg_message_length', 0),
                'in_degree': self.graph.in_degree(node),
                'out_degree': self.graph.out_degree(node),
                'total_degree': self.graph.in_degree(node) + self.graph.out_degree(node)
            }

        # 按消息数量排序
        sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['message_count'], reverse=True)

        return {
            'user_stats': user_stats,
            'top_active_users': sorted_users[:10],
            'total_users': len(user_stats)
        }

    def _calculate_centrality_metrics(self) -> Dict[str, Any]:
        """计算网络中心性指标"""
        if self.graph.number_of_nodes() == 0:
            return {}

        try:
            # 度中心性
            degree_centrality = nx.degree_centrality(self.graph)
            in_degree_centrality = nx.in_degree_centrality(self.graph)
            out_degree_centrality = nx.out_degree_centrality(self.graph)

            # 介数中心性
            betweenness_centrality = nx.betweenness_centrality(self.graph)

            # 接近中心性
            closeness_centrality = nx.closeness_centrality(self.graph)

            # PageRank
            pagerank = nx.pagerank(self.graph)

            # 特征向量中心性（使用无向图）
            if self.undirected_graph.number_of_nodes() > 0:
                try:
                    eigenvector_centrality = nx.eigenvector_centrality(self.undirected_graph, max_iter=1000)
                except:
                    eigenvector_centrality = {}
            else:
                eigenvector_centrality = {}

            # 找出各指标的前5名
            top_degree = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:5]
            top_betweenness = sorted(betweenness_centrality.items(), key=lambda x: x[1], reverse=True)[:5]
            top_closeness = sorted(closeness_centrality.items(), key=lambda x: x[1], reverse=True)[:5]
            top_pagerank = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:5]

            return {
                'degree_centrality': degree_centrality,
                'in_degree_centrality': in_degree_centrality,
                'out_degree_centrality': out_degree_centrality,
                'betweenness_centrality': betweenness_centrality,
                'closeness_centrality': closeness_centrality,
                'pagerank': pagerank,
                'eigenvector_centrality': eigenvector_centrality,
                'top_degree': [(self._get_user_name(uid), score) for uid, score in top_degree],
                'top_betweenness': [(self._get_user_name(uid), score) for uid, score in top_betweenness],
                'top_closeness': [(self._get_user_name(uid), score) for uid, score in top_closeness],
                'top_pagerank': [(self._get_user_name(uid), score) for uid, score in top_pagerank]
            }
        except Exception as e:
            logger.error(f"计算中心性指标失败: {e}")
            return {}

    def _detect_communities(self) -> Dict[str, Any]:
        """社区检测"""
        if self.undirected_graph.number_of_nodes() == 0:
            return {}

        try:
            # 使用Louvain算法进行社区检测
            partition = community_louvain.best_partition(self.undirected_graph)

            # 计算模块度
            modularity = community_louvain.modularity(partition, self.undirected_graph)

            # 按社区分组
            communities = defaultdict(list)
            for node, community_id in partition.items():
                communities[community_id].append({
                    'user_id': node,
                    'user_name': self._get_user_name(node),
                    'message_count': self.graph.nodes[node].get('message_count', 0)
                })

            # 按社区大小排序
            sorted_communities = sorted(communities.items(), key=lambda x: len(x[1]), reverse=True)

            return {
                'partition': partition,
                'modularity': modularity,
                'num_communities': len(communities),
                'communities': dict(communities),
                'sorted_communities': sorted_communities[:10],  # 前10个最大社区
                'community_sizes': [len(members) for members in communities.values()]
            }
        except Exception as e:
            logger.error(f"社区检测失败: {e}")
            return {}

    def _analyze_interaction_patterns(self) -> Dict[str, Any]:
        """分析互动模式"""
        if self.graph.number_of_edges() == 0:
            return {}

        # 互动强度分布
        weights = [data['weight'] for _, _, data in self.graph.edges(data=True)]
        interaction_counts = [data['interaction_count'] for _, _, data in self.graph.edges(data=True)]

        # 最强互动关系
        strongest_interactions = []
        for u, v, data in self.graph.edges(data=True):
            strongest_interactions.append({
                'from': self._get_user_name(u),
                'to': self._get_user_name(v),
                'weight': data['weight'],
                'interaction_count': data['interaction_count'],
                'reply_count': data['reply_count'],
                'mention_count': data['mention_count']
            })

        strongest_interactions.sort(key=lambda x: x['weight'], reverse=True)

        return {
            'avg_interaction_strength': sum(weights) / len(weights) if weights else 0,
            'max_interaction_strength': max(weights) if weights else 0,
            'min_interaction_strength': min(weights) if weights else 0,
            'total_interaction_count': sum(interaction_counts),
            'avg_interaction_count': sum(interaction_counts) / len(interaction_counts) if interaction_counts else 0,
            'strongest_interactions': strongest_interactions[:10]
        }

    def _identify_key_players(self) -> Dict[str, Any]:
        """识别关键节点和影响者"""
        if self.graph.number_of_nodes() == 0:
            return {}

        key_players = {}

        # 基于不同指标识别关键人物
        try:
            # 度中心性最高的用户（连接最多）
            degree_centrality = nx.degree_centrality(self.graph)
            most_connected = max(degree_centrality.items(), key=lambda x: x[1])

            # 介数中心性最高的用户（桥梁作用）
            betweenness_centrality = nx.betweenness_centrality(self.graph)
            bridge_player = max(betweenness_centrality.items(), key=lambda x: x[1])

            # PageRank最高的用户（影响力）
            pagerank = nx.pagerank(self.graph)
            most_influential = max(pagerank.items(), key=lambda x: x[1])

            # 出度最高的用户（主动互动者）
            out_degrees = dict(self.graph.out_degree())
            most_active_initiator = max(out_degrees.items(), key=lambda x: x[1])

            # 入度最高的用户（受欢迎者）
            in_degrees = dict(self.graph.in_degree())
            most_popular = max(in_degrees.items(), key=lambda x: x[1])

            key_players = {
                'most_connected': {
                    'user_id': most_connected[0],
                    'user_name': self._get_user_name(most_connected[0]),
                    'score': most_connected[1]
                },
                'bridge_player': {
                    'user_id': bridge_player[0],
                    'user_name': self._get_user_name(bridge_player[0]),
                    'score': bridge_player[1]
                },
                'most_influential': {
                    'user_id': most_influential[0],
                    'user_name': self._get_user_name(most_influential[0]),
                    'score': most_influential[1]
                },
                'most_active_initiator': {
                    'user_id': most_active_initiator[0],
                    'user_name': self._get_user_name(most_active_initiator[0]),
                    'score': most_active_initiator[1]
                },
                'most_popular': {
                    'user_id': most_popular[0],
                    'user_name': self._get_user_name(most_popular[0]),
                    'score': most_popular[1]
                }
            }
        except Exception as e:
            logger.error(f"识别关键人物失败: {e}")

        return key_players

    def _analyze_network_structure(self) -> Dict[str, Any]:
        """分析网络结构特征"""
        if self.graph.number_of_nodes() == 0:
            return {}

        try:
            # 基本网络统计
            num_nodes = self.graph.number_of_nodes()
            num_edges = self.graph.number_of_edges()

            # 密度
            density = nx.density(self.graph)

            # 连通性分析
            if self.undirected_graph.number_of_nodes() > 0:
                is_connected = nx.is_connected(self.undirected_graph)
                num_components = nx.number_connected_components(self.undirected_graph)
                largest_component_size = len(max(nx.connected_components(self.undirected_graph), key=len))
            else:
                is_connected = False
                num_components = 0
                largest_component_size = 0

            # 聚类系数
            clustering_coefficient = nx.average_clustering(self.undirected_graph) if self.undirected_graph.number_of_nodes() > 0 else 0

            # 平均路径长度（仅对连通图）
            if is_connected and num_nodes > 1:
                avg_path_length = nx.average_shortest_path_length(self.undirected_graph)
            else:
                avg_path_length = 0

            # 度分布
            degrees = [d for n, d in self.graph.degree()]
            avg_degree = sum(degrees) / len(degrees) if degrees else 0
            max_degree = max(degrees) if degrees else 0
            min_degree = min(degrees) if degrees else 0

            return {
                'num_nodes': num_nodes,
                'num_edges': num_edges,
                'density': density,
                'is_connected': is_connected,
                'num_components': num_components,
                'largest_component_size': largest_component_size,
                'clustering_coefficient': clustering_coefficient,
                'avg_path_length': avg_path_length,
                'avg_degree': avg_degree,
                'max_degree': max_degree,
                'min_degree': min_degree,
                'degree_distribution': degrees
            }
        except Exception as e:
            logger.error(f"分析网络结构失败: {e}")
            return {}

    def _generate_visualization_data(self) -> Dict[str, Any]:
        """生成可视化数据"""
        if self.graph.number_of_nodes() == 0:
            return {}

        try:
            # 节点数据
            nodes = []
            for node in self.graph.nodes():
                node_data = self.graph.nodes[node]
                nodes.append({
                    'id': node,
                    'name': self._get_user_name(node),
                    'message_count': node_data.get('message_count', 0),
                    'in_degree': self.graph.in_degree(node),
                    'out_degree': self.graph.out_degree(node),
                    'size': node_data.get('message_count', 1)  # 节点大小基于消息数
                })

            # 边数据
            edges = []
            for u, v, data in self.graph.edges(data=True):
                edges.append({
                    'source': u,
                    'target': v,
                    'weight': data.get('weight', 0),
                    'interaction_count': data.get('interaction_count', 0),
                    'width': data.get('weight', 0.1) * 10  # 边宽度基于权重
                })

            # 社区信息（如果有）
            communities_data = {}
            if hasattr(self, '_communities') and self._communities:
                communities_data = self._communities

            return {
                'nodes': nodes,
                'edges': edges,
                'communities': communities_data,
                'layout_suggestions': {
                    'spring': 'spring_layout',
                    'circular': 'circular_layout',
                    'kamada_kawai': 'kamada_kawai_layout'
                }
            }
        except Exception as e:
            logger.error(f"生成可视化数据失败: {e}")
            return {}

    def get_summary(self) -> Dict[str, Any]:
        """获取分析摘要"""
        if not self.is_analyzed:
            return {}

        results = self.results
        centrality = results.get('centrality_metrics', {})
        communities = results.get('communities', {})
        key_players = results.get('key_players', {})
        network_structure = results.get('network_structure', {})

        summary = {
            '总消息数': results.get('total_messages', 0),
            '总用户数': results.get('total_users', 0),
            '总互动关系数': results.get('total_interactions', 0),
            '网络密度': f"{network_structure.get('density', 0):.3f}",
            '聚类系数': f"{network_structure.get('clustering_coefficient', 0):.3f}",
            '社区数量': communities.get('num_communities', 0),
            '模块度': f"{communities.get('modularity', 0):.3f}",
            '最具影响力用户': key_players.get('most_influential', {}).get('user_name', '无'),
            '最受欢迎用户': key_players.get('most_popular', {}).get('user_name', '无'),
            '桥梁用户': key_players.get('bridge_player', {}).get('user_name', '无'),
            '平均度数': f"{network_structure.get('avg_degree', 0):.1f}",
            '是否连通': '是' if network_structure.get('is_connected', False) else '否'
        }

        return summary
