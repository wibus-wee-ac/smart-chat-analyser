"""
用户缓存管理器
用于缓存和管理聊天记录中的用户信息，提高@艾特识别的准确性
"""

import logging
import threading
import time
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta
from chatlog_client import ChatlogClient

logger = logging.getLogger(__name__)


class UserCache:
    """用户缓存管理器"""
    
    def __init__(self, chatlog_client: Optional[ChatlogClient] = None):
        """
        初始化用户缓存
        
        Args:
            chatlog_client: 聊天记录客户端实例
        """
        self.client = chatlog_client or ChatlogClient()
        self._lock = threading.RLock()
        
        # 缓存数据
        self._contacts: Dict[str, Dict] = {}  # userName -> contact info
        self._chatrooms: Dict[str, Dict] = {}  # chatroom id -> chatroom info
        self._chatroom_users: Dict[str, Set[str]] = {}  # chatroom id -> user set
        self._user_names: Dict[str, Set[str]] = {}  # userName -> {nickName, alias, remark}
        self._name_to_users: Dict[str, Set[str]] = {}  # name -> {userName1, userName2}
        
        # 缓存状态
        self._last_update: Optional[datetime] = None
        self._is_loading = False
        self._load_error: Optional[str] = None
        
    @property
    def is_loaded(self) -> bool:
        """检查缓存是否已加载"""
        with self._lock:
            return self._last_update is not None and not self._is_loading
    
    @property
    def last_update(self) -> Optional[datetime]:
        """获取最后更新时间"""
        with self._lock:
            return self._last_update
    
    @property
    def load_error(self) -> Optional[str]:
        """获取加载错误信息"""
        with self._lock:
            return self._load_error
    
    def load_cache(self, force_reload: bool = False) -> bool:
        """
        加载用户缓存
        
        Args:
            force_reload: 是否强制重新加载
            
        Returns:
            是否加载成功
        """
        with self._lock:
            if self._is_loading:
                logger.info("用户缓存正在加载中...")
                return False
                
            if self.is_loaded and not force_reload:
                logger.info("用户缓存已加载，跳过重复加载")
                return True
                
            self._is_loading = True
            self._load_error = None
            
        try:
            logger.info("开始加载用户缓存...")
            start_time = time.time()
            
            # 加载联系人
            contacts = self._load_contacts()
            
            # 加载群聊
            chatrooms = self._load_chatrooms()
            
            # 构建索引
            self._build_indexes(contacts, chatrooms)
            
            with self._lock:
                self._last_update = datetime.now()
                self._is_loading = False
                
            load_time = time.time() - start_time
            logger.info(f"用户缓存加载完成，耗时 {load_time:.2f}s")
            logger.info(f"缓存统计: {len(self._contacts)} 个联系人, {len(self._chatrooms)} 个群聊")
            
            return True
            
        except Exception as e:
            error_msg = f"用户缓存加载失败: {e}"
            logger.error(error_msg)
            
            with self._lock:
                self._load_error = error_msg
                self._is_loading = False
                
            return False
    
    def _load_contacts(self) -> List[Dict]:
        """加载联系人列表"""
        try:
            contacts = self.client.get_contacts()
            logger.info(f"加载了 {len(contacts)} 个联系人")
            return contacts
        except Exception as e:
            logger.error(f"加载联系人失败: {e}")
            return []
    
    def _load_chatrooms(self) -> List[Dict]:
        """加载群聊列表"""
        try:
            chatrooms = self.client.get_chatrooms()
            logger.info(f"加载了 {len(chatrooms)} 个群聊")
            return chatrooms
        except Exception as e:
            logger.error(f"加载群聊失败: {e}")
            return []
    
    def _build_indexes(self, contacts: List[Dict], chatrooms: List[Dict]):
        """构建索引"""
        with self._lock:
            # 清空现有缓存
            self._contacts.clear()
            self._chatrooms.clear()
            self._chatroom_users.clear()
            self._user_names.clear()
            self._name_to_users.clear()
            
            # 处理联系人
            for contact in contacts:
                user_name = contact.get('userName', '')
                if not user_name:
                    continue
                    
                self._contacts[user_name] = contact
                
                # 收集所有可能的名称
                names = set()
                if contact.get('nickName'):
                    names.add(contact['nickName'])
                if contact.get('alias'):
                    names.add(contact['alias'])
                if contact.get('remark'):
                    names.add(contact['remark'])
                
                self._user_names[user_name] = names
                
                # 建立名称到用户的反向索引
                for name in names:
                    if name not in self._name_to_users:
                        self._name_to_users[name] = set()
                    self._name_to_users[name].add(user_name)
            
            # 处理群聊
            for chatroom in chatrooms:
                chatroom_id = chatroom.get('name', '')  # 群聊ID通常在name字段
                if not chatroom_id:
                    continue
                    
                self._chatrooms[chatroom_id] = chatroom
                
                # 处理群聊用户
                users = chatroom.get('users', [])
                user_set = set()
                
                for user in users:
                    user_name = user.get('userName', '')
                    if user_name:
                        user_set.add(user_name)
                        
                        # 如果这个用户不在联系人中，也要建立索引
                        if user_name not in self._user_names:
                            names = set()
                            if user.get('nickName'):
                                names.add(user['nickName'])
                            if user.get('displayName'):
                                names.add(user['displayName'])
                                
                            self._user_names[user_name] = names
                            
                            # 建立反向索引
                            for name in names:
                                if name not in self._name_to_users:
                                    self._name_to_users[name] = set()
                                self._name_to_users[name].add(user_name)
                
                self._chatroom_users[chatroom_id] = user_set
    
    def is_valid_mention(self, mention_name: str, chatroom_id: Optional[str] = None) -> bool:
        """
        检查@艾特是否为有效用户
        
        Args:
            mention_name: 被@的名称
            chatroom_id: 群聊ID（如果是群聊消息）
            
        Returns:
            是否为有效的@艾特
        """
        if not self.is_loaded:
            logger.warning("用户缓存未加载，无法验证@艾特")
            return True  # 缓存未加载时，保守地认为是有效的
        
        with self._lock:
            # 检查是否为已知的用户名称
            if mention_name in self._name_to_users:
                # 如果指定了群聊，检查用户是否在该群聊中
                if chatroom_id and chatroom_id in self._chatroom_users:
                    mentioned_users = self._name_to_users[mention_name]
                    chatroom_users = self._chatroom_users[chatroom_id]
                    return bool(mentioned_users & chatroom_users)
                return True
            
            return False
    
    def get_user_info(self, user_name: str) -> Optional[Dict]:
        """
        获取用户信息
        
        Args:
            user_name: 用户名
            
        Returns:
            用户信息字典
        """
        with self._lock:
            return self._contacts.get(user_name)
    
    def get_chatroom_info(self, chatroom_id: str) -> Optional[Dict]:
        """
        获取群聊信息
        
        Args:
            chatroom_id: 群聊ID
            
        Returns:
            群聊信息字典
        """
        with self._lock:
            return self._chatrooms.get(chatroom_id)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        with self._lock:
            return {
                'is_loaded': self.is_loaded,
                'last_update': self._last_update.isoformat() if self._last_update else None,
                'load_error': self._load_error,
                'contacts_count': len(self._contacts),
                'chatrooms_count': len(self._chatrooms),
                'total_names': len(self._name_to_users),
                'is_loading': self._is_loading
            }
    
    def search_users(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索用户
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            匹配的用户列表
        """
        if not self.is_loaded:
            return []
        
        results = []
        query_lower = query.lower()
        
        with self._lock:
            for user_name, names in self._user_names.items():
                # 检查用户名是否匹配
                if query_lower in user_name.lower():
                    contact = self._contacts.get(user_name, {})
                    results.append({
                        'userName': user_name,
                        'nickName': contact.get('nickName', ''),
                        'alias': contact.get('alias', ''),
                        'remark': contact.get('remark', ''),
                        'match_type': 'userName'
                    })
                    continue
                
                # 检查名称是否匹配
                for name in names:
                    if query_lower in name.lower():
                        contact = self._contacts.get(user_name, {})
                        results.append({
                            'userName': user_name,
                            'nickName': contact.get('nickName', ''),
                            'alias': contact.get('alias', ''),
                            'remark': contact.get('remark', ''),
                            'match_type': 'name',
                            'matched_name': name
                        })
                        break
                
                if len(results) >= limit:
                    break
        
        return results[:limit]


# 全局用户缓存实例
_user_cache: Optional[UserCache] = None


def get_user_cache() -> UserCache:
    """获取全局用户缓存实例"""
    global _user_cache
    if _user_cache is None:
        _user_cache = UserCache()
    return _user_cache


def init_user_cache(chatlog_client: Optional[ChatlogClient] = None) -> UserCache:
    """
    初始化全局用户缓存
    
    Args:
        chatlog_client: 聊天记录客户端实例
        
    Returns:
        用户缓存实例
    """
    global _user_cache
    _user_cache = UserCache(chatlog_client)
    return _user_cache
