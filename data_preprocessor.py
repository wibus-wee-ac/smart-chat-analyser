"""
数据预处理模块
过滤垃圾数据和无用信息，提高分析质量
"""

import re
from typing import List, Dict, Any, Set
import logging

logger = logging.getLogger(__name__)


class DataPreprocessor:
    """数据预处理器"""
    
    def __init__(self):
        """初始化数据预处理器"""
        # 垃圾内容模式
        self.garbage_patterns = [
            # 插件相关
            r'\[X1a0He WeChat Plugin\]',
            r'\[.*?Plugin\]',
            r'\[.*?插件\]',
            r'\[.*?\]'
            
            # 系统消息
            r'系统消息',
            r'System Message',
            r'系统通知',
            
            # 微信系统消息
            r'.*?撤回了一条消息',
            r'.*?withdrew a message',
            r'.*?拍了拍.*?',
            r'.*?patted.*?',
            r'.*?加入了群聊',
            r'.*?joined the group chat',
            r'.*?退出了群聊',
            r'.*?left the group chat',
            r'.*?邀请.*?加入了群聊',
            r'.*?invited.*?to join the group chat',
            r'.*?修改群名为.*?',
            r'.*?changed the group name to.*?',
            
            # 红包和转账
            r'.*?发出红包，请在手机上查看',
            r'.*?sent a red packet',
            r'.*?收到转账.*?',
            r'.*?received a transfer',
            r'.*?向你转账.*?',
            r'.*?transferred.*?to you',
            
            # 语音和视频通话
            r'.*?发起了语音通话',
            r'.*?started a voice call',
            r'.*?发起了视频通话',
            r'.*?started a video call',
            r'通话时长.*?',
            r'Call duration.*?',
            
            # 位置分享
            r'.*?分享了位置',
            r'.*?shared location',
            r'.*?共享了实时位置',
            r'.*?shared live location',
            
            # 文件分享
            r'.*?分享了文件',
            r'.*?shared a file',
            r'.*?发送了.*?个文件',
            r'.*?sent.*?files?',
            
            # 小程序和链接
            r'.*?分享了小程序',
            r'.*?shared a mini program',
            r'.*?分享了链接',
            r'.*?shared a link',
            
            # 表情包
            r'.*?发送了一个表情',
            r'.*?sent a sticker',
            r'.*?发送了动画表情',
            r'.*?sent an animated emoji',
            
            # 其他系统消息
            r'.*?开启了朋友验证',
            r'.*?enabled friend verification',
            r'.*?关闭了朋友验证',
            r'.*?disabled friend verification',
            r'以上是打招呼的内容',
            r'The above is the greeting content',
        ]
        
        # 编译正则表达式
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.garbage_patterns]
        
        # 垃圾词汇
        self.garbage_words = {
            # 无意义的重复字符
            '哈哈哈哈哈哈哈哈哈哈', '嘻嘻嘻嘻嘻嘻嘻嘻', '呵呵呵呵呵呵呵呵',
            '啦啦啦啦啦啦啦啦', '嘿嘿嘿嘿嘿嘿嘿嘿', '嗯嗯嗯嗯嗯嗯嗯嗯',
            
            # 纯符号
            # '。。。。。。。。。。', '，，，，，，，，，，', '！！！！！！！！！！',
            # '？？？？？？？？？？', '……………………', '————————————',
            
            # 纯数字（超过10位）
            # 这个通过长度检查处理
            
            # 测试内容
            'test', 'Test', 'TEST', '测试', '测试测试测试',
            
            # 无意义短语
            # '没什么', '没事', '算了', '不说了', '懒得说',
            # '随便', '无所谓', '不知道', '不清楚', '不确定',
        }
        
        # 最小有效内容长度
        self.min_content_length = 2
        
        # 最大有效内容长度（过滤超长垃圾内容）
        self.max_content_length = 300
    
    def preprocess_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        预处理数据，过滤垃圾内容
        
        Args:
            data: 原始聊天记录数据
            
        Returns:
            过滤后的数据
        """
        logger.info(f"开始数据预处理，原始数据量: {len(data)}")
        
        filtered_data = []
        
        for item in data:
            if self._is_valid_message(item):
                # 清理内容
                cleaned_item = self._clean_message_content(item)
                if cleaned_item:
                    filtered_data.append(cleaned_item)
        
        removed_count = len(data) - len(filtered_data)
        removal_rate = (removed_count / len(data)) * 100 if data else 0
        
        logger.info(f"数据预处理完成，过滤后数据量: {len(filtered_data)}")
        logger.info(f"移除了 {removed_count} 条垃圾数据 ({removal_rate:.1f}%)")
        
        return filtered_data
    
    def _is_valid_message(self, item: Dict[str, Any]) -> bool:
        """
        判断消息是否有效

        Args:
            item: 消息项

        Returns:
            是否有效
        """
        content = item.get('content', '').strip()
        msg_type = item.get('type', 0)
        sender = item.get('sender', '')
        is_self = item.get('isSelf', False)

        # 检查内容长度
        if len(content) < self.min_content_length:
            return False

        if len(content) > self.max_content_length:
            return False

        # 检查消息类型（通常文本消息是type=1）
        # 过滤掉非文本消息
        if msg_type != 1:
            return False

        # 检查发送者（考虑自己发送的消息）
        if not is_self and (not sender or sender.strip() == ''):
            return False
        
        # 检查是否匹配垃圾模式
        for pattern in self.compiled_patterns:
            if pattern.search(content):
                return False
        
        # 检查是否为垃圾词汇
        if content in self.garbage_words:
            return False
        
        # 检查是否为纯数字（超过10位）
        if content.isdigit() and len(content) > 4:
            return False
        
        # # 检查是否为纯符号
        # if self._is_pure_symbols(content):
        #     return False
        
        # # 检查是否为重复字符
        # if self._is_repetitive_content(content):
        #     return False
        
        return True
    
    # def _is_pure_symbols(self, content: str) -> bool:
    #     """检查是否为纯符号"""
    #     # 移除空格后检查
    #     content_no_space = content.replace(' ', '')
    #     if not content_no_space:
    #         return True
        
    #     # 检查是否只包含标点符号和特殊字符
    #     symbol_pattern = re.compile(r'^[^\w\u4e00-\u9fa5]+$')
    #     return bool(symbol_pattern.match(content_no_space))
    
    # def _is_repetitive_content(self, content: str) -> bool:
    #     """检查是否为重复内容"""
    #     # 检查单字符重复（如：哈哈哈哈哈哈哈哈）
    #     if len(content) >= 8:
    #         unique_chars = set(content)
    #         if len(unique_chars) <= 2:  # 只有1-2个不同字符
    #             return True
        
    #     # 检查短语重复（如：哈哈哈哈哈哈）
    #     if len(content) >= 6:
    #         # 检查2字符重复
    #         for i in range(len(content) - 1):
    #             substr = content[i:i+2]
    #             if content.count(substr) >= 3:  # 重复3次以上
    #                 return True
            
    #         # 检查3字符重复
    #         for i in range(len(content) - 2):
    #             substr = content[i:i+3]
    #             if content.count(substr) >= 2:  # 重复2次以上
    #                 return True
        
    #     return False
    
    def _clean_message_content(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理消息内容

        Args:
            item: 消息项

        Returns:
            清理后的消息项
        """
        cleaned_item = item.copy()
        content = item.get('content', '')

        # 处理自己发送的消息（补充发送者信息）
        is_self = item.get('isSelf', False)
        if is_self:
            # 为自己发送的消息添加标识
            cleaned_item['sender'] = 'Me'  # 特殊标识符表示自己
            cleaned_item['senderName'] = '我'  # 显示名称
                

        # 移除多余的空白字符
        content = re.sub(r'\s+', ' ', content).strip()

        # 移除特殊的Unicode字符
        content = re.sub(r'[\u200b-\u200f\u2028-\u202f\u205f-\u206f]', '', content)

        # 移除零宽字符
        content = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', content)

        # 标准化引号
        content = content.replace('"', '"').replace('"', '"')
        content = content.replace(''', "'").replace(''', "'")

        # 移除过多的重复标点
        # content = re.sub(r'([。！？，；：])\1{2,}', r'\1', content)
        # content = re.sub(r'([.!?,:;])\1{2,}', r'\1', content)

        cleaned_item['content'] = content

        # 如果清理后内容太短，返回None
        if len(content.strip()) < self.min_content_length:
            return None

        return cleaned_item
    
    def get_filter_stats(self, original_data: List[Dict], filtered_data: List[Dict]) -> Dict[str, Any]:
        """
        获取过滤统计信息
        
        Args:
            original_data: 原始数据
            filtered_data: 过滤后数据
            
        Returns:
            统计信息
        """
        original_count = len(original_data)
        filtered_count = len(filtered_data)
        removed_count = original_count - filtered_count
        removal_rate = (removed_count / original_count) * 100 if original_count > 0 else 0
        
        # 分析移除的内容类型
        removed_items = []
        for item in original_data:
            if not self._is_valid_message(item):
                removed_items.append(item)
        
        # 统计移除原因
        removal_reasons = {
            '系统消息': 0,
            '插件消息': 0,
            '内容过短': 0,
            '内容过长': 0,
            '其他': 0
        }
        
        for item in removed_items:
            content = item.get('content', '')
            
            if any(pattern.search(content) for pattern in self.compiled_patterns):
                if 'Plugin' in content or '插件' in content:
                    removal_reasons['插件消息'] += 1
                elif '系统' in content or 'System' in content:
                    removal_reasons['系统消息'] += 1
                else:
                    removal_reasons['其他'] += 1
            # elif self._is_repetitive_content(content):
            #     removal_reasons['重复内容'] += 1
            # elif self._is_pure_symbols(content):
            #     removal_reasons['纯符号'] += 1
            elif len(content.strip()) < self.min_content_length:
                removal_reasons['内容过短'] += 1
            elif len(content) > self.max_content_length:
                removal_reasons['内容过长'] += 1
            else:
                removal_reasons['其他'] += 1
        
        return {
            'original_count': original_count,
            'filtered_count': filtered_count,
            'removed_count': removed_count,
            'removal_rate': removal_rate,
            'removal_reasons': removal_reasons
        }
