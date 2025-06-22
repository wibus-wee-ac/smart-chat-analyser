"""
消息内容解析工具
用于解析聊天消息中的@艾特、链接、表情等特殊内容
"""

import re
from typing import Dict, List, Any, Optional


class MessageContentParser:
    """消息内容解析器，用于分离@艾特和实际内容"""

    def __init__(self, user_cache=None):
        """
        初始化消息解析器

        Args:
            user_cache: 用户缓存实例，用于验证@艾特的有效性
        """
        # 改进的@艾特正则模式
        # 1. 基础模式：@后面跟非空格字符
        self.mention_pattern = re.compile(r'@[^\s@]+')

        # 2. 邮箱模式：用于排除邮箱地址
        self.email_pattern = re.compile(r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

        # 3. 改进的@艾特模式：排除明显的邮箱格式
        # @后面跟1-20个字符（中文、英文、数字、下划线），但不能是邮箱格式
        self.improved_mention_pattern = re.compile(r'@(?!.*\.[a-zA-Z]{2,})[\w\u4e00-\u9fff]{1,20}(?=\s|$|[^\w\u4e00-\u9fff])')

        # 其他模式
        self.url_pattern = re.compile(r'https?://[^\s]+')
        self.emoji_bracket_pattern = re.compile(r'\[[^\]]*\]')

        # 用户缓存
        self.user_cache = user_cache
    
    def parse_message(self, content: str, chatroom_id: Optional[str] = None) -> Dict[str, Any]:
        """
        解析消息内容，分离@艾特和实际内容

        Args:
            content: 原始消息内容
            chatroom_id: 群聊ID（用于验证@艾特的有效性）

        Returns:
            解析结果字典，包含：
            - mentions: 艾特的用户列表（已验证有效性）
            - raw_mentions: 原始@艾特列表（未验证）
            - clean_content: 移除艾特后的纯内容
            - original_content: 原始内容
            - has_mentions: 是否包含@艾特
            - urls: 链接列表（可选）
            - emojis: 表情符号列表（可选）
        """
        # 使用改进的正则表达式查找@艾特
        raw_mentions = self.improved_mention_pattern.findall(content)

        # 验证@艾特的有效性
        valid_mentions = []
        if self.user_cache and self.user_cache.is_loaded:
            for mention in raw_mentions:
                mention_name = mention[1:]  # 移除@符号
                if self.user_cache.is_valid_mention(mention_name, chatroom_id):
                    valid_mentions.append(mention_name)
        else:
            # 如果没有用户缓存，使用基础过滤
            valid_mentions = self._filter_mentions_basic(raw_mentions)

        # 查找所有链接
        urls = self.url_pattern.findall(content)

        # 查找所有[表情]格式的表情符号
        emojis = self.emoji_bracket_pattern.findall(content)

        # 移除@艾特，保留其他内容
        clean_content = self.improved_mention_pattern.sub('', content).strip()
        # 清理多余空格
        clean_content = re.sub(r'\s+', ' ', clean_content)

        return {
            'mentions': valid_mentions,  # 验证后的有效@艾特
            'raw_mentions': [mention[1:] for mention in raw_mentions],  # 原始@艾特
            'clean_content': clean_content,
            'original_content': content,
            'has_mentions': len(valid_mentions) > 0,
            'urls': urls,
            'emojis': [emoji[1:-1] for emoji in emojis],  # 移除[]符号
            'has_urls': len(urls) > 0,
            'has_emojis': len(emojis) > 0
        }
    
    def _filter_mentions_basic(self, raw_mentions: List[str]) -> List[str]:
        """
        基础@艾特过滤（当用户缓存不可用时使用）

        Args:
            raw_mentions: 原始@艾特列表（包含@符号）

        Returns:
            过滤后的用户名列表
        """
        valid_mentions = []
        for mention in raw_mentions:
            mention_name = mention[1:]  # 移除@符号

            # 基础过滤规则
            if self._is_likely_email(mention):
                continue  # 跳过邮箱
            if len(mention_name) > 20:
                continue  # 跳过过长的名称
            if not mention_name:
                continue  # 跳过空名称

            valid_mentions.append(mention_name)

        return valid_mentions

    def _is_likely_email(self, mention: str) -> bool:
        """检查@艾特是否可能是邮箱地址"""
        return bool(self.email_pattern.match(mention))

    def extract_mentions_only(self, content: str, chatroom_id: Optional[str] = None) -> List[str]:
        """
        仅提取@艾特用户名

        Args:
            content: 消息内容
            chatroom_id: 群聊ID（用于验证）

        Returns:
            被艾特的用户名列表（已验证有效性）
        """
        parsed = self.parse_message(content, chatroom_id)
        return parsed['mentions']
    
    def remove_mentions(self, content: str) -> str:
        """
        移除@艾特，返回纯内容

        Args:
            content: 消息内容

        Returns:
            移除@艾特后的内容
        """
        clean_content = self.improved_mention_pattern.sub('', content).strip()
        return re.sub(r'\s+', ' ', clean_content)

    def set_user_cache(self, user_cache):
        """
        设置用户缓存

        Args:
            user_cache: 用户缓存实例
        """
        self.user_cache = user_cache
    
    def get_content_statistics(self, messages: List[str]) -> Dict[str, Any]:
        """
        获取消息内容统计信息
        
        Args:
            messages: 消息内容列表
            
        Returns:
            统计信息字典
        """
        total_messages = len(messages)
        messages_with_mentions = 0
        messages_with_urls = 0
        messages_with_emojis = 0
        all_mentions = []
        all_urls = []
        all_emojis = []
        
        for message in messages:
            parsed = self.parse_message(message)
            
            if parsed['has_mentions']:
                messages_with_mentions += 1
                all_mentions.extend(parsed['mentions'])
            
            if parsed['has_urls']:
                messages_with_urls += 1
                all_urls.extend(parsed['urls'])
            
            if parsed['has_emojis']:
                messages_with_emojis += 1
                all_emojis.extend(parsed['emojis'])
        
        return {
            'total_messages': total_messages,
            'messages_with_mentions': messages_with_mentions,
            'messages_with_urls': messages_with_urls,
            'messages_with_emojis': messages_with_emojis,
            'mention_rate': messages_with_mentions / total_messages if total_messages > 0 else 0,
            'url_rate': messages_with_urls / total_messages if total_messages > 0 else 0,
            'emoji_rate': messages_with_emojis / total_messages if total_messages > 0 else 0,
            'unique_mentions': len(set(all_mentions)),
            'unique_urls': len(set(all_urls)),
            'unique_emojis': len(set(all_emojis)),
            'total_mentions': len(all_mentions),
            'total_urls': len(all_urls),
            'total_emojis': len(all_emojis)
        }


# 创建全局实例，方便其他模块使用
message_parser = MessageContentParser()


def init_message_parser_with_cache(user_cache):
    """
    使用用户缓存初始化全局消息解析器

    Args:
        user_cache: 用户缓存实例
    """
    global message_parser
    message_parser = MessageContentParser(user_cache)
