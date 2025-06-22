"""
聊天记录分析器主应用
集成所有服务和API
"""

import logging
import sys
import os
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('chatlog_analyzer.log')
    ]
)

logger = logging.getLogger(__name__)

def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'chatlog-analyzer-secret-key'

    # 配置CORS - 允许所有来源
    CORS(app,
         origins="*",
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

    # 初始化SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")

    return app, socketio

def initialize_services():
    """初始化所有服务"""
    logger.info("正在初始化服务...")

    try:
        # 初始化模型管理器
        from core.model_manager import get_model_manager
        model_manager = get_model_manager()
        logger.info("模型管理器初始化完成")

        # 初始化任务队列
        from core.task_queue import get_task_queue
        task_queue = get_task_queue()
        logger.info("任务队列初始化完成")

        # 初始化各种服务
        from services.data_preprocessing_service import get_data_preprocessing_service
        from services.analysis_service import get_analysis_service
        from services.visualization_service import get_visualization_service

        preprocessing_service = get_data_preprocessing_service()
        analysis_service = get_analysis_service()
        visualization_service = get_visualization_service()

        logger.info("数据处理服务初始化完成")

        # 初始化任务处理器
        from core.analysis_task_handler import get_analysis_task_handler
        task_handler = get_analysis_task_handler()
        logger.info("任务处理器初始化完成")

        # 启动任务队列工作线程
        task_queue.start_worker()
        logger.info("任务队列工作线程已启动")

        # 初始化预加载管理器
        from core.preloader import get_preload_manager
        preload_manager = get_preload_manager()
        logger.info("预加载管理器初始化完成")

        # 启动预加载（异步，不阻塞启动）
        from config import config
        if config.AUTO_PRELOAD_MODELS or config.AUTO_PRELOAD_USER_CACHE:
            start_preloading(preload_manager)
        else:
            logger.info("自动预加载已禁用")

        return {
            'model_manager': model_manager,
            'task_queue': task_queue,
            'preprocessing_service': preprocessing_service,
            'analysis_service': analysis_service,
            'visualization_service': visualization_service,
            'task_handler': task_handler,
            'preload_manager': preload_manager
        }

    except Exception as e:
        logger.error(f"服务初始化失败: {e}")
        raise

def start_preloading(preload_manager):
    """启动预加载"""
    import threading

    def preload_worker():
        try:
            logger.info("开始自动预加载...")
            # 使用预加载管理器统一管理预加载
            result = preload_manager.preload_all()
            if result['success']:
                logger.info("自动预加载完成")
            else:
                logger.error(f"自动预加载失败: {result}")

        except Exception as e:
            logger.error(f"自动预加载异常: {e}")

    # 在后台线程中执行预加载
    preload_thread = threading.Thread(target=preload_worker, daemon=True, name="Preloader")
    preload_thread.start()

def register_routes(app, socketio, services):
    """注册路由"""
    # 注册API路由
    from api.routes import create_api_routes
    api_blueprint = create_api_routes(services)
    app.register_blueprint(api_blueprint)

    # 设置WebSocket管理器
    from core.websocket_manager import get_websocket_manager
    websocket_manager = get_websocket_manager()
    websocket_manager.set_socketio(socketio)
    websocket_manager.start_redis_subscription()

    # 将websocket_manager添加到services中以便后续清理
    services['websocket_manager'] = websocket_manager

    logger.info("路由和WebSocket管理器注册完成")

def main():
    """主函数"""
    logger.info("启动聊天记录分析器...")

    try:
        # 导入配置
        from config import config

        # 创建Flask应用
        app, socketio = create_app()

        # 初始化服务
        services = initialize_services()

        # 注册路由
        register_routes(app, socketio, services)

        logger.info("所有服务初始化完成，启动Web服务器...")

        # 启动服务器 - 使用配置文件中的端口
        socketio.run(app, host=config.HOST, port=config.PORT, debug=config.DEBUG)
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        sys.exit(1)
    finally:
        # 清理资源
        try:
            if 'services' in locals():
                services['task_queue'].stop_worker()
                services['preprocessing_service'].shutdown()
                services['analysis_service'].shutdown()
                if 'websocket_manager' in services:
                    services['websocket_manager'].stop_redis_subscription()
            logger.info("资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")

if __name__ == '__main__':
    main()
