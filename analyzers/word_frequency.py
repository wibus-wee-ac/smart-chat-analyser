"""
高频词汇分析器
分析聊天记录中最常出现的词汇和短语
使用最全面的中文停用词库和智能重复词汇过滤
"""

import jieba
import re
import os
from collections import Counter
from typing import Dict, List, Any, Tuple, Optional, Set
from .base import BaseAnalyzer
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.message_parser import message_parser
import logging

logger = logging.getLogger(__name__)


class WordFrequencyAnalyzer(BaseAnalyzer):
    """高频词汇分析器"""

    def __init__(self, top_n: int = 50, min_length: int = 2):
        """
        初始化高频词汇分析器

        Args:
            top_n: 返回前N个高频词
            min_length: 词汇最小长度
        """
        super().__init__(
            name="高频词汇分析器",
            description="分析聊天记录中最常出现的词汇和短语，使用最全面的停用词库"
        )
        self.top_n = top_n
        self.min_length = min_length

        # 使用全局消息内容解析器
        self.content_parser = message_parser

        # 加载停用词库
        self.stop_words = self._load_stopwords()

        # 重复词汇模式（用于过滤哈哈哈、嘻嘻嘻等）
        self.repetitive_patterns = [
            r'^(.)\1{2,}$',  # 3个或以上相同字符，如：哈哈哈、嘻嘻嘻
            r'^(.{2})\1{1,}$',  # 重复的双字符，如：哈哈哈哈、嘿嘿嘿嘿
            r'^(.{3})\1{1,}$',  # 重复的三字符，如：哈哈哈哈哈哈
        ]

    def _load_stopwords(self) -> Set[str]:
        """
        加载停用词库

        Returns:
            停用词集合
        """
        stop_words = set()

        # 停用词文件列表（按优先级排序）
        stopword_files = [
            'cn_stopwords.txt',      # 中文停用词表
            'hit_stopwords.txt',     # 哈工大停用词表
            'baidu_stopwords.txt',   # 百度停用词表
        ]

        # 获取当前文件所在目录的父目录（项目根目录）
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        stopwords_dir = os.path.join(current_dir, 'data', 'stopwords')

        for filename in stopword_files:
            filepath = os.path.join(stopwords_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    words = f.read().strip().split('\n')
                    stop_words.update(word.strip() for word in words if word.strip())
                logger.info(f"成功加载停用词文件: {filename}, 词汇数: {len(words)}")
            except FileNotFoundError:
                logger.warning(f"停用词文件未找到: {filename}")
            except Exception as e:
                logger.error(f"加载停用词文件失败 {filename}: {e}")

        # 添加常见的无意义词汇
        additional_stopwords = {
            # 语气词和感叹词
            '啊', '呀', '哎', '哦', '嗯', '唉', '哈', '呵', '嘿', '喂', '哟', '咦', '哇', '呜', '嗨',
            # 重复字符
            '哈哈', '嘻嘻', '呵呵', '嘿嘿', '啦啦', '呀呀', '哎哎', '嗯嗯',
            # 表情相关
            '捂脸', '笑哭', '微笑', '大哭', '害羞', '愤怒', '惊讶', '思考', '困', '晕', '汗', '赞',
            # 无意义的短词
            '额', '呃', '嗯', '哦', '啊', '呀', '哎', '唉', '哈', '呵', '嘿', '喂', '哟', '咦', '哇', '呜',
            # 常见的聊天用词
            '然后', '就是', '这样', '那样', '这个', '那个', '什么', '怎么', '为什么', '可以', '不是',
            '应该', '可能', '觉得', '感觉', '知道', '看到', '听到', '想要', '需要', '希望'
        }
        stop_words.update(additional_stopwords)

        logger.info(f"总共加载停用词: {len(stop_words)} 个")
        return stop_words

    def analyze(self, data: List[Dict], task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行高频词汇分析

        Args:
            data: 聊天记录数据列表

        Returns:
            分析结果字典
        """
        logger.info("开始高频词汇分析")

        # 提取所有文本内容，同时收集@艾特信息
        all_text = ""
        all_mentions = []
        parsed_messages = []

        for item in data:
            content = item.get('content', '')
            if content:
                # 解析消息内容
                parsed = self.content_parser.parse_message(content)
                parsed_messages.append(parsed)

                # 收集纯内容用于词频分析
                clean_content = parsed['clean_content']
                if clean_content:
                    all_text += clean_content + " "

                # 收集@艾特信息（用于社交网络分析）
                if parsed['has_mentions']:
                    all_mentions.extend(parsed['mentions'])

        # 文本预处理
        processed_text = self._preprocess_text(all_text)

        # 分词
        words = self._segment_words(processed_text)

        # 统计词频
        word_counts = Counter(words)

        # 获取高频词
        top_words = word_counts.most_common(self.top_n)

        # 按词性分类统计
        word_by_type = self._categorize_words(words)

        # 短语分析：优先识别重复的完整句子，然后提取常规短语
        repeated_sentences = self._extract_repeated_sentences(all_text)
        regular_phrases = self._extract_phrases(words)

        # 合并重复句子和常规短语
        all_phrases = repeated_sentences + regular_phrases
        phrase_counts = Counter(all_phrases)
        top_phrases = phrase_counts.most_common(min(20, len(phrase_counts)))

        # 统计@艾特信息
        mention_counts = Counter(all_mentions)
        top_mentions = mention_counts.most_common(20)

        results = {
            'total_words': len(words),
            'unique_words': len(word_counts),
            'top_words': top_words,
            'word_by_type': word_by_type,
            'top_phrases': top_phrases,
            'word_frequency_distribution': dict(word_counts.most_common(100)),
            # 新增@艾特统计信息
            'mentions_stats': {
                'total_mentions': len(all_mentions),
                'unique_mentions': len(mention_counts),
                'top_mentions': top_mentions,
                'messages_with_mentions': sum(1 for msg in parsed_messages if msg['has_mentions']),
                'total_messages': len(parsed_messages)
            }
        }

        logger.info(f"高频词汇分析完成，共分析 {len(words)} 个词汇，{len(all_mentions)} 个@艾特")
        return results
    
    def _preprocess_text(self, text: str) -> str:
        """
        文本预处理

        Args:
            text: 原始文本（已经移除@艾特的纯内容）

        Returns:
            预处理后的文本
        """
        # 移除表情符号 [xxx] 格式
        text = re.sub(r'\[[^\]]*\]', '', text)

        # 移除特殊符号和表情符号，但保留标点符号
        # 保留中文、英文、数字、空格和常见标点符号
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s，。！？；：、""''（）【】《》〈〉「」『』〔〕［］｛｝〖〗,.!?;:\'"()\\[\\]{}]', '', text)

        # 移除多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _segment_words(self, text: str) -> List[str]:
        """
        分词处理

        Args:
            text: 预处理后的文本

        Returns:
            分词结果列表
        """
        # 使用jieba分词
        words = jieba.lcut(text)

        # 过滤停用词和短词
        filtered_words = []
        for word in words:
            word = word.strip()
            if (len(word) >= self.min_length and
                word not in self.stop_words and
                not word.isdigit() and
                not self._is_emoji_word(word) and
                not self._is_repetitive_word(word) and  # 过滤重复词汇
                not self._is_meaningless_word(word)):   # 过滤无意义词汇
                filtered_words.append(word)

        return filtered_words
    
    def _is_emoji_word(self, word: str) -> bool:
        """
        判断是否为表情符号词汇
        
        Args:
            word: 词汇
            
        Returns:
            是否为表情符号词汇
        """
        # 表情符号特征词
        emoji_keywords = {
            '捂脸', '笑哭', '微笑', '大哭', '害羞', '愤怒', '惊讶', '思考', '困', '晕', '汗', '赞', '心', '玫瑰', '礼物', '蛋糕', '太阳', '月亮', '星星', '花', '草', '树', '猫', '狗', '猪', '牛', '马', '羊', '鸡', '鸭', '鱼', '虾', '蟹', '蛇', '龙', '虎', '兔', '猴', '鼠'
        }
        
        # 检查是否包含表情符号特征
        if word in emoji_keywords:
            return True
        
        # 检查是否包含表情符号相关的字符
        emoji_chars = ['😀', '😃', '😄', '😁', '😆', '😅', '😂', '🤣', '😊', '😇', '🙂', '🙃', '😉', '😌', '😍', '🥰', '😘', '😗', '😙', '😚', '😋', '😛', '😝', '😜', '🤪', '🤨', '🧐', '🤓', '😎', '🤩', '🥳', '😏', '😒', '😞', '😔', '😟', '😕', '🙁', '☹️', '😣', '😖', '😫', '😩', '🥺', '😢', '😭', '😤', '😠', '😡', '🤬', '🤯', '😳', '🥵', '🥶', '😱', '😨', '😰', '😥', '😓', '🤗', '🤔', '🤭', '🤫', '🤥', '😶', '😐', '😑', '😯', '😦', '😧', '😮', '😲', '🥱', '😴', '🤤', '😪', '😵', '🤐', '🥴', '🤢', '🤮', '🤧', '😷', '🤒', '🤕', '🤑', '🤠']
        
        for char in emoji_chars:
            if char in word:
                return True
        
        return False

    def _is_repetitive_word(self, word: str) -> bool:
        """
        判断是否为重复词汇（如：哈哈哈、嘻嘻嘻）

        Args:
            word: 词汇

        Returns:
            是否为重复词汇
        """
        for pattern in self.repetitive_patterns:
            if re.match(pattern, word):
                return True
        return False

    def _is_meaningless_word(self, word: str) -> bool:
        """
        判断是否为无意义词汇

        Args:
            word: 词汇

        Returns:
            是否为无意义词汇
        """
        # 检查是否全是标点符号
        if re.match(r'^[^\w\u4e00-\u9fa5]+$', word):
            return True

        # 检查是否为单个字符重复
        if len(word) >= 3 and len(set(word)) == 1:
            return True

        # 检查是否为常见的无意义组合
        meaningless_patterns = [
            r'^[哈嘻呵嘿啦呀哎嗯哦唉咦哇呜嗨额呃]+$',  # 纯语气词组合
            r'^[。，、；：！？""''（）【】]+$',           # 纯标点符号
            r'^\d+[个只条件次遍趟回下上]$',              # 数字+量词
        ]

        for pattern in meaningless_patterns:
            if re.match(pattern, word):
                return True

        return False

    def _categorize_words(self, words: List[str]) -> Dict[str, List[Tuple[str, int]]]:
        """
        按词性分类词汇
        
        Args:
            words: 词汇列表
            
        Returns:
            按词性分类的词汇统计
        """
        # 简单的词性分类（基于长度和特征）
        categories = {
            'short_words': [],  # 2-3个字符
            'medium_words': [],  # 4-6个字符
            'long_words': [],   # 7个字符以上
            'numbers': [],      # 数字
            'english': []       # 英文单词
        }
        
        word_counts = Counter(words)
        
        for word, count in word_counts.items():
            if re.match(r'^[0-9]+$', word):
                categories['numbers'].append((word, count))
            elif re.match(r'^[a-zA-Z]+$', word):
                categories['english'].append((word, count))
            elif len(word) <= 3:
                categories['short_words'].append((word, count))
            elif len(word) <= 6:
                categories['medium_words'].append((word, count))
            else:
                categories['long_words'].append((word, count))
        
        # 按频率排序
        for category in categories:
            categories[category] = sorted(categories[category], key=lambda x: x[1], reverse=True)
        
        return categories
    
    def _extract_repeated_sentences(self, text: str, min_repeat: int = 3, min_length: int = 10) -> List[str]:
        """
        提取重复出现的完整句子

        Args:
            text: 原始文本
            min_repeat: 最小重复次数
            min_length: 句子最小长度

        Returns:
            重复句子列表
        """
        repeated_sentences = []

        # 按句号、感叹号、问号等分割句子
        sentences = re.split(r'[。！？\n]+', text)
        sentence_counts = Counter()

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) >= min_length:
                # 移除多余空格
                clean_sentence = re.sub(r'\s+', '', sentence)
                if clean_sentence:
                    sentence_counts[clean_sentence] += 1

        # 找出重复次数达到阈值的句子
        for sentence, count in sentence_counts.items():
            if count >= min_repeat:
                # 为每次重复添加到结果中
                repeated_sentences.extend([sentence] * count)

        return repeated_sentences

    def _extract_phrases(self, words: List[str], max_length: int = 3) -> List[str]:
        """
        提取短语

        Args:
            words: 词汇列表
            max_length: 短语最大长度

        Returns:
            短语列表
        """
        phrases = []
        for i in range(len(words) - max_length + 1):
            for length in range(2, max_length + 1):
                if i + length <= len(words):
                    phrase = ''.join(words[i:i+length])
                    if len(phrase) >= 4:  # 短语至少4个字符
                        phrases.append(phrase)

        return phrases
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取分析摘要

        Returns:
            分析摘要字典
        """
        if not self.is_analyzed:
            return {}

        top_words = self.results.get('top_words', [])
        top_phrases = self.results.get('top_phrases', [])
        mentions_stats = self.results.get('mentions_stats', {})

        summary = {
            '总词汇数': self.results.get('total_words', 0),
            '唯一词汇数': self.results.get('unique_words', 0),
            '最高频词汇': top_words[0][0] if top_words else '无',
            '最高频词汇频率': top_words[0][1] if top_words else 0,
            '最高频短语': top_phrases[0][0] if top_phrases else '无',
            '最高频短语频率': top_phrases[0][1] if top_phrases else 0,
            '前10高频词汇': [word for word, _ in top_words[:10]]
        }

        # 添加@艾特统计信息
        if mentions_stats:
            summary.update({
                '总@艾特数': mentions_stats.get('total_mentions', 0),
                '唯一被@用户数': mentions_stats.get('unique_mentions', 0),
                '包含@艾特的消息数': mentions_stats.get('messages_with_mentions', 0),
                '最常被@用户': mentions_stats.get('top_mentions', [{}])[0][0] if mentions_stats.get('top_mentions') else '无'
            })

        return summary

    def get_mentions_data(self) -> Dict[str, Any]:
        """
        获取@艾特数据，用于社交网络分析

        Returns:
            @艾特数据字典
        """
        if not self.is_analyzed:
            return {}

        return self.results.get('mentions_stats', {})