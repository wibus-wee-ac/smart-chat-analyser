"""
聊天记录API客户端
用于从HTTP API获取聊天记录数据
"""

import requests
import json
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ChatlogClient:
    """聊天记录API客户端"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5030"):
        """
        初始化客户端
        
        Args:
            base_url: API服务器地址
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': 'ChatlogAnalyzer/1.0',
            'Accept': 'application/json'
        })
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> list:
        """
        发送HTTP请求
        
        Args:
            endpoint: API端点
            params: 请求参数
            
        Returns:
            响应数据（优先返回data['items']，否则返回list或dict）
        """
        url = f"{self.base_url}{endpoint}"
        
        # 确保返回JSON格式
        if params is None:
            params = {}
        params['format'] = 'json'
        
        try:
            logger.info(f"请求URL: {url}")
            logger.info(f"请求参数: {params}")
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            # 自动提取items字段
            if isinstance(data, dict) and 'items' in data:
                return data['items']
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
            raise
    
    def get_chatlog(self, 
                   time: Optional[str] = None,
                   talker: Optional[str] = None,
                   limit: Optional[int] = None,
                   offset: Optional[int] = None,
                   format: str = "json") -> list:
        """
        获取聊天记录
        
        Args:
            time: 时间范围，格式为 YYYY-MM-DD 或 YYYY-MM-DD~YYYY-MM-DD
            talker: 聊天对象标识
            limit: 返回记录数量
            offset: 分页偏移量
            format: 输出格式，支持 json、csv 或纯文本
        
        Returns:
            聊天记录列表（List[Dict]）
        """
        params = {}
        if time:
            params['time'] = time
        if talker:
            params['talker'] = talker
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        if format:
            params['format'] = format
        return self._make_request('/api/v1/chatlog', params)
    
    def get_contacts(self) -> list:
        """
        获取联系人列表
        
        Returns:
            联系人列表（List[Dict]），每个元素结构如：
            {
                "userName": str,
                "alias": str,
                "remark": str,
                "nickName": str,
                "isFriend": bool
            }
        """
        return self._make_request('/api/v1/contact')
    
    def get_chatrooms(self) -> list:
        """
        获取群聊列表
        
        Returns:
            群聊列表（List[Dict]），每个元素结构如：
            {
                "name": str,
                "owner": str,
                "users": List[Dict],
                "remark": str,
                "nickName": str
            }
        """
        return self._make_request('/api/v1/chatroom')
    
    def get_sessions(self) -> list:
        """
        获取会话列表
        
        Returns:
            会话列表（List[Dict]），每个元素结构如：
            {
                "userName": str,
                "nOrder": int,
                "nickName": str,
                "content": str,
                "nTime": str
            }
        """
        return self._make_request('/api/v1/session')
    
    def get_chatlog_by_date_range(self, 
                                 start_date: str, 
                                 end_date: str,
                                 talker: Optional[str] = None,
                                 limit: Optional[int] = None) -> List[Dict]:
        """
        按日期范围获取聊天记录
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            talker: 聊天对象标识
            limit: 返回记录数量
            
        Returns:
            聊天记录列表
        """
        time_range = f"{start_date}~{end_date}"
        return self.get_chatlog(time=time_range, talker=talker, limit=limit)
    
    def get_chatlog_by_talker(self, 
                             talker: str,
                             days: int = 30,
                             limit: Optional[int] = None) -> List[Dict]:
        """
        获取指定聊天对象的聊天记录
        
        Args:
            talker: 聊天对象标识
            days: 获取最近几天的记录
            limit: 返回记录数量
            
        Returns:
            聊天记录列表
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        return self.get_chatlog_by_date_range(start_date, end_date, talker, limit)
    
    def test_connection(self) -> bool:
        """
        测试API连接
        
        Returns:
            连接是否成功
        """
        try:
            # 尝试获取会话列表来测试连接
            self.get_sessions()
            logger.info("API连接测试成功")
            return True
        except Exception as e:
            logger.error(f"API连接测试失败: {e}")
            return False


def main():
    """测试函数"""
    # 创建客户端实例
    client = ChatlogClient()
    
    # 测试连接
    if client.test_connection():
        print("✅ API连接成功")
        
        # 获取会话列表
        try:
            sessions = client.get_sessions()
            print(f"✅ 获取到 {len(sessions)} 个会话")
            if sessions:
                print("📝 会话列表示例:")
                print(json.dumps(sessions[0], ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ 获取会话列表失败: {e}")
        
        # 获取联系人列表
        try:
            contacts = client.get_contacts()
            print(f"✅ 获取到 {len(contacts)} 个联系人")
            if contacts:
                print("📝 联系人列表示例:")
                print(json.dumps(contacts[0], ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ 获取联系人列表失败: {e}")
        
        # 获取最近的聊天记录示例（使用第一个会话的talker）
        try:
            if sessions:
                first_session = sessions[0]
                talker = first_session.get('talker', '')
                if talker:
                    print(f"🔍 尝试获取talker '{talker}' 的聊天记录...")
                    chatlogs = client.get_chatlog(talker=talker, limit=5)
                    print(f"✅ 获取到 {len(chatlogs)} 条聊天记录")
                    
                    # 打印第一条记录的结构
                    if chatlogs:
                        print("📝 聊天记录示例:")
                        print(json.dumps(chatlogs[0], ensure_ascii=False, indent=2))
                else:
                    print("⚠️ 会话中没有找到talker信息")
            else:
                print("⚠️ 没有可用的会话")
                
        except Exception as e:
            print(f"❌ 获取聊天记录失败: {e}")
    else:
        print("❌ API连接失败，请检查服务器是否运行")


if __name__ == "__main__":
    main() 