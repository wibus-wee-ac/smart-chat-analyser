"""
消息内容解析工具
用于解析聊天消息中的@艾特、链接、表情等特殊内容
"""

import re
from typing import Dict, List, Any


class MessageContentParser:
    """消息内容解析器，用于分离@艾特和实际内容"""
    
    def __init__(self):
        # @艾特的正则模式：@后面跟非空格字符，直到遇到空格
        self.mention_pattern = re.compile(r'@[^\s]+')
        
        # 可以扩展其他模式
        self.url_pattern = re.compile(r'https?://[^\s]+')
        self.emoji_bracket_pattern = re.compile(r'\[[^\]]*\]')
    
    def parse_message(self, content: str) -> Dict[str, Any]:
        """
        解析消息内容，分离@艾特和实际内容
        
        Args:
            content: 原始消息内容
            
        Returns:
            解析结果字典，包含：
            - mentions: 艾特的用户列表
            - clean_content: 移除艾特后的纯内容
            - original_content: 原始内容
            - has_mentions: 是否包含@艾特
            - urls: 链接列表（可选）
            - emojis: 表情符号列表（可选）
        """
        # 查找所有@艾特
        mentions = self.mention_pattern.findall(content)
        
        # 查找所有链接
        urls = self.url_pattern.findall(content)
        
        # 查找所有[表情]格式的表情符号
        emojis = self.emoji_bracket_pattern.findall(content)
        
        # 移除@艾特，保留其他内容
        clean_content = self.mention_pattern.sub('', content).strip()
        # 清理多余空格
        clean_content = re.sub(r'\s+', ' ', clean_content)
        
        return {
            'mentions': [mention[1:] for mention in mentions],  # 移除@符号
            'clean_content': clean_content,
            'original_content': content,
            'has_mentions': len(mentions) > 0,
            'urls': urls,
            'emojis': [emoji[1:-1] for emoji in emojis],  # 移除[]符号
            'has_urls': len(urls) > 0,
            'has_emojis': len(emojis) > 0
        }
    
    def extract_mentions_only(self, content: str) -> List[str]:
        """
        仅提取@艾特用户名
        
        Args:
            content: 消息内容
            
        Returns:
            被艾特的用户名列表
        """
        mentions = self.mention_pattern.findall(content)
        return [mention[1:] for mention in mentions]  # 移除@符号
    
    def remove_mentions(self, content: str) -> str:
        """
        移除@艾特，返回纯内容
        
        Args:
            content: 消息内容
            
        Returns:
            移除@艾特后的内容
        """
        clean_content = self.mention_pattern.sub('', content).strip()
        return re.sub(r'\s+', ' ', clean_content)
    
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
