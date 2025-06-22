# 聊天记录分析器 (Chatlog Analyzer)

一个用于分析微信聊天记录的Python工具，支持高频词汇分析、情感分析、时间模式分析等功能。

## 功能特性

- 📊 **高频词汇分析**: 统计最常使用的词汇和短语
- 🕐 **时间模式分析**: 分析聊天活跃时间段和频率分布
- 😊 **情感分析**: 分析聊天记录的情感倾向
- 🗣️ **话题聚类**: 使用主题建模发现主要聊天话题
- 👥 **社交网络分析**: 分析互动关系和活跃度
- 📈 **个性化分析**: 个人语言特征和行为模式识别

## 安装和设置

### 1. 克隆项目
```bash
git clone <repository-url>
cd chatlog-analyser
```

### 2. 创建虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 启动聊天记录API服务
确保你的聊天记录API服务正在运行（默认地址：http://127.0.0.1:5030）

## 架构特性

- 🏗️ **微服务架构**: 模块化设计，服务独立部署
- 🚀 **异步任务队列**: 基于Redis的任务队列，支持长时间分析
- 🔄 **实时进度推送**: WebSocket实时推送任务进度和状态
- 🧩 **插件化分析器**: 支持动态加载自定义分析器
- 📊 **标准化图表数据**: 返回JSON格式图表数据，支持前端渲染
- 🔧 **模型单例管理**: 智能模型缓存，避免重复加载
- 📈 **并发处理优化**: 多线程并发执行分析任务
- ⚡ **智能预加载**: 支持模型预加载功能，提升响应速度和用户体验

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动Redis服务
```bash
# macOS (使用Homebrew)
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# 或使用Docker
docker run -d -p 6379:6379 redis:alpine
```

### 3. 启动服务
```bash
python run.py
```

### 4. 使用API

#### 提交分析任务
```bash
curl -X POST http://localhost:5000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "chatlog_analysis",
    "task_data": {
      "talker": "某个聊天对象",
      "days": 30,
      "analyzers": ["word_frequency", "sentiment", "time_pattern"]
    }
  }'
```

#### 查询任务状态
```bash
curl http://localhost:5000/api/v1/tasks/{task_id}
```

#### 获取分析结果
```bash
curl http://localhost:5000/api/v1/tasks/{task_id}/result
```

## 使用方法

### Python客户端使用

```python
from examples.api_usage import ChatlogAnalyzerClient

# 创建客户端
client = ChatlogAnalyzerClient("http://localhost:5000")

# 提交分析任务
task_id = client.submit_analysis_task(
    talker="某个聊天对象",
    days=30,
    analyzers=["word_frequency", "sentiment", "time_pattern"]
)

# 等待任务完成并获取结果
result = client.wait_for_task_completion(task_id)
print("分析完成！")

# 查看分析结果
analysis_results = result['result']['analysis_results']
chart_data = result['result']['chart_data']
```

### WebSocket实时监控

```python
from examples.api_usage import WebSocketClient

# 创建WebSocket客户端
ws_client = WebSocketClient("http://localhost:5000")
ws_client.connect()

# 订阅任务进度更新
ws_client.subscribe_task(task_id)
```

### 自定义分析器

```python
from analyzers.base import BaseAnalyzer
from core.analyzer_registry import register_analyzer

@register_analyzer("custom_analyzer", {"category": "custom"})
class CustomAnalyzer(BaseAnalyzer):
    def __init__(self):
        super().__init__(
            name="自定义分析器",
            description="自定义分析逻辑"
        )

    def run(self, data):
        # 实现自定义分析逻辑
        return {"custom_result": "分析结果"}
```

## 项目结构

```
chatlog-analyser/
├── analyzers/              # 分析器模块
│   ├── base.py            # 分析器基类
│   ├── word_frequency.py  # 词频分析
│   ├── sentiment.py       # 情感分析
│   ├── time_pattern.py    # 时间模式分析
│   └── social_network.py  # 社交网络分析
├── core/                  # 核心服务
│   ├── model_manager.py   # 模型管理器
│   ├── task_queue.py      # 任务队列
│   ├── websocket_manager.py # WebSocket管理
│   ├── analyzer_registry.py # 分析器注册表
│   └── analysis_task_handler.py # 任务处理器
├── services/              # 业务服务层
│   ├── data_preprocessing_service.py # 数据预处理服务
│   ├── analysis_service.py # 分析服务
│   └── visualization_service.py # 可视化服务
├── api/                   # API层
│   └── routes.py          # REST API路由
├── data/                  # 数据文件
│   └── stopwords/         # 停用词库
│       ├── cn_stopwords.txt      # 中文停用词
│       ├── hit_stopwords.txt     # 哈工大停用词
│       └── baidu_stopwords.txt   # 百度停用词
├── examples/              # 使用示例
│   └── api_usage.py       # API使用示例
├── logs/                  # 日志目录
├── models/                # 模型缓存目录
├── charts/                # 图表输出目录
├── app.py                 # 主应用
├── run.py                 # 启动脚本
├── config.py              # 配置文件
├── chatlog_client.py      # 聊天记录客户端
├── data_preprocessor.py   # 数据预处理器
└── requirements.txt       # 项目依赖
```

## API接口

### 任务管理
- `POST /api/v1/tasks` - 提交分析任务
- `GET /api/v1/tasks/{task_id}` - 获取任务状态
- `GET /api/v1/tasks/{task_id}/result` - 获取任务结果
- `POST /api/v1/tasks/{task_id}/cancel` - 取消任务

### 系统状态
- `GET /api/v1/health` - 健康检查
- `GET /api/v1/system/stats` - 系统统计信息
- `GET /api/v1/queue/stats` - 队列统计信息

### 分析器管理
- `GET /api/v1/analyzers` - 获取可用分析器
- `GET /api/v1/analyzers/{name}` - 获取分析器信息

### 模型管理
- `GET /api/v1/models/info` - 获取模型信息
- `POST /api/v1/models/clear` - 清除模型缓存
- `POST /api/v1/models/preload` - 预加载模型
- `GET /api/v1/models/preload/status` - 获取预加载状态
- `POST /api/v1/models/preload/cancel` - 取消预加载任务

## 模型预加载功能

为了提升用户体验，系统支持模型预加载功能，可以在空闲时间提前加载AI模型，避免首次使用时的等待时间。

### 特性
- **自动预加载**: 应用启动时自动预加载常用模型
- **手动预加载**: 提供API接口手动触发模型加载
- **进度监控**: 实时监控预加载进度和状态
- **优先级管理**: 按优先级顺序加载模型
- **错误处理**: 完善的错误处理和重试机制

### 配置选项
在 `config.py` 中可以配置：
```python
AUTO_PRELOAD_MODELS = True  # 是否启用自动预加载
```

### 使用示例
```python
# 预加载指定模型
curl -X POST http://localhost:6142/api/v1/models/preload \
  -H "Content-Type: application/json" \
  -d '{"model_key": "sentiment_model"}'

# 预加载所有模型
curl -X POST http://localhost:6142/api/v1/models/preload \
  -H "Content-Type: application/json" \
  -d '{}'

# 获取预加载状态
curl http://localhost:6142/api/v1/models/preload/status

# 取消预加载
curl -X POST http://localhost:6142/api/v1/models/preload/cancel \
  -H "Content-Type: application/json" \
  -d '{"model_key": "bertopic_model"}'
```

## 功能状态

### ✅ 已完成
- [x] 高频词汇分析模块
- [x] 情感分析模块（支持深度学习模型）
- [x] 时间模式分析模块
- [x] 社交网络分析模块
- [x] 数据可视化模块（JSON格式输出）
- [x] 微服务架构
- [x] 异步任务队列
- [x] WebSocket实时通信
- [x] 插件化分析器系统
- [x] REST API接口
- [x] 模型管理和缓存
- [x] 模型预加载功能
- [x] 话题聚类模块（BERTopic集成）

### 📋 计划中
- [ ] 多语言支持
- [ ] 分布式部署支持
- [ ] 更多可视化图表类型
- [ ] 数据持久化存储

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License 