"""
Flask-RESTX API路由定义
包含所有REST API端点，自动生成OpenAPI文档
"""

from flask import request
from flask_restx import Api, Resource, Namespace
from datetime import datetime
import logging
import requests

from .models import create_api_models

logger = logging.getLogger(__name__)

def create_api_routes(services):
    """创建API路由和文档"""
    # 创建Flask-RESTX API实例
    api = Api(
        version='1.0',
        title='Chatlog Analyzer API',
        description='聊天记录分析系统API接口文档',
        doc='/docs/',  # Swagger UI 路径
        prefix='/api/v1'
    )
    
    # 创建API模型
    models = create_api_models(api)
    
    # 获取服务实例
    task_queue = services['task_queue']
    model_manager = services['model_manager']
    analysis_service = services['analysis_service']
    preprocessing_service = services['preprocessing_service']
    visualization_service = services['visualization_service']
    preload_manager = services['preload_manager']
    
    # 创建命名空间
    health_ns = Namespace('health', description='健康检查相关接口')
    tasks_ns = Namespace('tasks', description='任务管理相关接口')
    queue_ns = Namespace('queue', description='队列管理相关接口')
    system_ns = Namespace('system', description='系统状态相关接口')
    analyzers_ns = Namespace('analyzers', description='分析器管理相关接口')
    models_ns = Namespace('models', description='模型管理相关接口')
    cache_ns = Namespace('user-cache', description='用户缓存相关接口')
    preload_ns = Namespace('preload', description='预加载管理相关接口')
    proxy_ns = Namespace('chatlog', description='聊天记录代理接口')
    
    # 注册命名空间
    api.add_namespace(health_ns)
    api.add_namespace(tasks_ns)
    api.add_namespace(queue_ns)
    api.add_namespace(system_ns)
    api.add_namespace(analyzers_ns)
    api.add_namespace(models_ns)
    api.add_namespace(cache_ns)
    api.add_namespace(preload_ns)
    api.add_namespace(proxy_ns)
    
    # 健康检查接口
    @health_ns.route('')
    class HealthCheck(Resource):
        @health_ns.doc('health_check')
        @health_ns.marshal_with(models['health_response'])
        def get(self):
            """健康检查"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "services": {
                    "task_queue": task_queue.is_running,
                    "model_manager": True,
                    "preprocessing_service": True,
                    "analysis_service": True,
                    "visualization_service": True
                }
            }
    
    # 任务管理接口
    @tasks_ns.route('')
    class TasksList(Resource):
        @tasks_ns.doc('get_tasks')
        @tasks_ns.param('status', '状态过滤器', type='string', enum=['pending', 'running', 'completed', 'failed', 'cancelled'])
        @tasks_ns.param('limit', '返回数量限制', type='int', default=20)
        @tasks_ns.param('offset', '偏移量', type='int', default=0)
        @tasks_ns.marshal_with(models['tasks_list_response'])
        @tasks_ns.response(400, 'Bad Request', models['error_response'])
        @tasks_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """获取任务列表"""
            try:
                # 获取查询参数
                status_filter = request.args.get('status')
                limit = int(request.args.get('limit', 20))
                offset = int(request.args.get('offset', 0))

                # 参数验证
                if limit > 100:
                    limit = 100
                if limit < 1:
                    limit = 1
                if offset < 0:
                    offset = 0

                # 验证状态过滤器
                valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
                if status_filter and status_filter not in valid_statuses:
                    api.abort(400, f"无效的状态过滤器，支持的状态: {', '.join(valid_statuses)}")

                # 获取任务列表
                tasks = task_queue.get_all_tasks(status_filter, limit, offset)
                total_count = task_queue.get_task_count(status_filter)

                # 转换为字典格式
                task_list = [task.to_dict(include_result=False) for task in tasks]

                return {
                    "tasks": task_list,
                    "pagination": {
                        "total": total_count,
                        "limit": limit,
                        "offset": offset,
                        "has_more": offset + len(task_list) < total_count
                    },
                    "filters": {
                        "status": status_filter
                    },
                    "timestamp": datetime.now().isoformat()
                }

            except ValueError as e:
                api.abort(400, f"参数错误: {str(e)}")
            except Exception as e:
                logger.error(f"获取任务列表失败: {e}")
                api.abort(500, str(e))
        
        @tasks_ns.doc('submit_task')
        @tasks_ns.expect(models['task_request'])
        @tasks_ns.marshal_with(models['task_submit_response'])
        @tasks_ns.response(400, 'Bad Request', models['error_response'])
        @tasks_ns.response(500, 'Internal Server Error', models['error_response'])
        def post(self):
            """提交分析任务"""
            try:
                data = request.get_json()
                
                if not data:
                    api.abort(400, "请求数据为空")
                
                # 设置默认任务类型
                task_type = data.get('task_type', 'chatlog_analysis')
                task_data = data.get('task_data', {})
                
                # 验证必要参数
                if task_type == 'chatlog_analysis':
                    if not task_data.get('talker') and not task_data.get('limit'):
                        api.abort(400, "聊天记录分析任务需要提供 talker 或 limit 参数")
                
                # 提交任务
                task_id = task_queue.submit_task(task_type, task_data)

                # 获取任务信息以获得群聊名称
                task_info = task_queue.get_task_status(task_id)

                return {
                    "task_id": task_id,
                    "status": "submitted",
                    "message": "任务已提交",
                    "task_type": task_type,
                    "submitted_at": datetime.now().isoformat(),
                    "chat_name": task_info.chat_name if task_info else None
                }
                
            except Exception as e:
                logger.error(f"提交任务失败: {e}")
                api.abort(500, str(e))
    
    @tasks_ns.route('/<string:task_id>')
    class TaskDetail(Resource):
        @tasks_ns.doc('get_task_status')
        @tasks_ns.marshal_with(models['task_result_response'])
        @tasks_ns.response(404, 'Task Not Found', models['error_response'])
        @tasks_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self, task_id):
            """获取任务状态"""
            try:
                task_info = task_queue.get_task_status(task_id)
                
                if not task_info:
                    api.abort(404, "任务不存在")
                
                return task_info.to_dict()
                
            except Exception as e:
                logger.error(f"获取任务状态失败: {e}")
                api.abort(500, str(e))
    
    @tasks_ns.route('/<string:task_id>/result')
    class TaskResult(Resource):
        @tasks_ns.doc('get_task_result')
        @tasks_ns.marshal_with(models['task_result_response'])
        @tasks_ns.response(400, 'Task Not Completed', models['error_response'])
        @tasks_ns.response(404, 'Task Not Found', models['error_response'])
        @tasks_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self, task_id):
            """获取任务结果"""
            try:
                task_info = task_queue.get_task_status(task_id)
                
                if not task_info:
                    api.abort(404, "任务不存在")
                
                from core.task_queue import TaskStatus
                if task_info.status != TaskStatus.COMPLETED:
                    api.abort(400, "任务尚未完成")
                
                return {
                    "task_id": task_id,
                    "status": task_info.status.value,
                    "result": task_info.result,
                    "completed_at": task_info.completed_at.isoformat() if task_info.completed_at else None,
                    "chat_name": task_info.chat_name
                }
                
            except Exception as e:
                logger.error(f"获取任务结果失败: {e}")
                api.abort(500, str(e))
    
    @tasks_ns.route('/<string:task_id>/cancel')
    class TaskCancel(Resource):
        @tasks_ns.doc('cancel_task')
        @tasks_ns.marshal_with(models['task_cancel_response'])
        @tasks_ns.response(400, 'Cannot Cancel Task', models['error_response'])
        @tasks_ns.response(404, 'Task Not Found', models['error_response'])
        @tasks_ns.response(500, 'Internal Server Error', models['error_response'])
        def post(self, task_id):
            """取消任务"""
            try:
                task_info = task_queue.get_task_status(task_id)
                
                if not task_info:
                    api.abort(404, "任务不存在")
                
                from core.task_queue import TaskStatus
                if task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    api.abort(400, "任务已完成，无法取消")
                
                # 更新任务状态为已取消
                task_info.status = TaskStatus.CANCELLED
                task_info.completed_at = datetime.now()
                task_info.message = "任务已被用户取消"
                task_queue._save_task_info(task_info)
                
                return {
                    "task_id": task_id,
                    "status": "cancelled",
                    "message": "任务已取消"
                }
                
            except Exception as e:
                logger.error(f"取消任务失败: {e}")
                api.abort(500, str(e))
    
    # 队列统计接口
    @queue_ns.route('/stats')
    class QueueStats(Resource):
        @queue_ns.doc('get_queue_stats')
        @queue_ns.marshal_with(models['queue_stats_response'])
        @queue_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """获取队列统计信息"""
            try:
                stats = task_queue.get_queue_stats()
                model_info = model_manager.get_model_info()

                return {
                    "queue": stats,
                    "models": model_info,
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"获取队列统计失败: {e}")
                api.abort(500, str(e))

    # 系统统计接口
    @system_ns.route('/stats')
    class SystemStats(Resource):
        @system_ns.doc('get_system_stats')
        @system_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """获取系统统计信息"""
            try:
                return {
                    "task_queue": task_queue.get_queue_stats(),
                    "model_manager": model_manager.get_model_info(),
                    "analysis_service": analysis_service.get_service_stats(),
                    "preprocessing_service": preprocessing_service.get_preprocessing_stats(),
                    "visualization_service": visualization_service.get_service_stats(),
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"获取系统统计失败: {e}")
                api.abort(500, str(e))

    # 分析器管理接口
    @analyzers_ns.route('')
    class AnalyzersList(Resource):
        @analyzers_ns.doc('get_analyzers')
        @analyzers_ns.marshal_with(models['analyzers_response'])
        @analyzers_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """获取可用分析器列表"""
            try:
                analyzers = analysis_service.get_available_analyzers()
                analyzer_info = {}

                for analyzer_name in analyzers:
                    try:
                        analyzer_info[analyzer_name] = analysis_service.get_analyzer_info(analyzer_name)
                    except Exception as e:
                        analyzer_info[analyzer_name] = {"error": str(e)}

                return {
                    "analyzers": analyzers,
                    "analyzer_info": analyzer_info,
                    "total_count": len(analyzers)
                }

            except Exception as e:
                logger.error(f"获取分析器列表失败: {e}")
                api.abort(500, str(e))

    @analyzers_ns.route('/<string:analyzer_name>')
    class AnalyzerDetail(Resource):
        @analyzers_ns.doc('get_analyzer_info')
        @analyzers_ns.marshal_with(models['analyzer_info'])
        @analyzers_ns.response(404, 'Analyzer Not Found', models['error_response'])
        @analyzers_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self, analyzer_name):
            """获取特定分析器信息"""
            try:
                info = analysis_service.get_analyzer_info(analyzer_name)
                return info

            except ValueError as e:
                api.abort(404, str(e))
            except Exception as e:
                logger.error(f"获取分析器信息失败: {e}")
                api.abort(500, str(e))

    # 模型管理接口
    @models_ns.route('/info')
    class ModelInfo(Resource):
        @models_ns.doc('get_model_info')
        @models_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """获取模型信息"""
            try:
                info = model_manager.get_model_info()
                return info

            except Exception as e:
                logger.error(f"获取模型信息失败: {e}")
                api.abort(500, str(e))

    @models_ns.route('/clear')
    class ModelClear(Resource):
        @models_ns.doc('clear_models')
        @models_ns.expect(models['model_clear_request'], validate=False)
        @models_ns.response(500, 'Internal Server Error', models['error_response'])
        def post(self):
            """清除模型缓存"""
            try:
                data = request.get_json() or {}
                model_key = data.get('model_key')

                if model_key:
                    model_manager.clear_model(model_key)
                    message = f"已清除模型: {model_key}"
                else:
                    model_manager.clear_all_models()
                    message = "已清除所有模型"

                return {
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"清除模型失败: {e}")
                api.abort(500, str(e))

    @models_ns.route('/preload')
    class ModelPreload(Resource):
        @models_ns.doc('preload_models')
        @models_ns.expect(models['model_preload_request'], validate=False)
        @models_ns.response(400, 'Bad Request', models['error_response'])
        @models_ns.response(500, 'Internal Server Error', models['error_response'])
        def post(self):
            """预加载模型"""
            try:
                data = request.get_json() or {}
                model_key = data.get('model_key')
                force = data.get('force', False)

                if model_key:
                    # 预加载指定模型
                    success = model_manager.preload_model(model_key, force=force)
                    if success:
                        return {
                            "message": f"开始预加载模型: {model_key}",
                            "model_key": model_key,
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        api.abort(400, f"无法预加载模型: {model_key}")
                else:
                    # 预加载所有模型
                    results = model_manager.preload_all_models(force=force)
                    return {
                        "message": "开始批量预加载模型",
                        "results": results,
                        "timestamp": datetime.now().isoformat()
                    }

            except Exception as e:
                logger.error(f"预加载模型失败: {e}")
                api.abort(500, str(e))

    @models_ns.route('/preload/status')
    class ModelPreloadStatus(Resource):
        @models_ns.doc('get_preload_status')
        @models_ns.param('model_key', '模型键名', type='string')
        @models_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """获取预加载状态"""
            try:
                model_key = request.args.get('model_key')
                status = model_manager.get_preload_status(model_key)

                return {
                    "status": status,
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"获取预加载状态失败: {e}")
                api.abort(500, str(e))

    @models_ns.route('/preload/cancel')
    class ModelPreloadCancel(Resource):
        @models_ns.doc('cancel_preload')
        @models_ns.expect(models['model_preload_request'])
        @models_ns.response(400, 'Bad Request', models['error_response'])
        @models_ns.response(500, 'Internal Server Error', models['error_response'])
        def post(self):
            """取消预加载任务"""
            try:
                data = request.get_json() or {}
                model_key = data.get('model_key')

                if not model_key:
                    api.abort(400, "缺少model_key参数")

                success = model_manager.cancel_preload(model_key)

                if success:
                    return {
                        "message": f"已取消模型预加载: {model_key}",
                        "model_key": model_key,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "message": f"无法取消模型预加载: {model_key}",
                        "model_key": model_key,
                        "timestamp": datetime.now().isoformat()
                    }

            except Exception as e:
                logger.error(f"取消预加载失败: {e}")
                api.abort(500, str(e))

    # 用户缓存接口
    @cache_ns.route('/status')
    class UserCacheStatus(Resource):
        @cache_ns.doc('get_user_cache_status')
        @cache_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """获取用户缓存状态"""
            try:
                status = preload_manager.get_user_cache_stats()
                preload_status = preload_manager.get_preload_status()

                return {
                    "cache_status": status,
                    "preload_status": preload_status.get('user_cache', {}),
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"获取用户缓存状态失败: {e}")
                api.abort(500, str(e))

    @cache_ns.route('/reload')
    class UserCacheReload(Resource):
        @cache_ns.doc('reload_user_cache')
        @cache_ns.response(500, 'Internal Server Error', models['error_response'])
        def post(self):
            """重新加载用户缓存"""
            try:
                result = preload_manager.reload_user_cache()

                if result['success']:
                    return {
                        "message": "用户缓存重新加载成功",
                        "result": result,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    api.abort(500, f"用户缓存重新加载失败: {result.get('error', '未知错误')}")

            except Exception as e:
                logger.error(f"重新加载用户缓存失败: {e}")
                api.abort(500, str(e))

    @cache_ns.route('/search')
    class UserSearch(Resource):
        @cache_ns.doc('search_users')
        @cache_ns.param('q', '搜索关键词', required=True, type='string')
        @cache_ns.param('limit', '返回数量限制', type='int', default=10)
        @cache_ns.marshal_with(models['user_search_response'])
        @cache_ns.response(400, 'Bad Request', models['error_response'])
        @cache_ns.response(503, 'Service Unavailable', models['error_response'])
        @cache_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """搜索用户"""
            try:
                query = request.args.get('q', '').strip()
                limit = int(request.args.get('limit', 10))

                if not query:
                    api.abort(400, "缺少搜索关键词")

                if limit > 50:
                    limit = 50
                if limit < 1:
                    limit = 1

                # 获取用户缓存
                from core.user_cache import get_user_cache
                user_cache = get_user_cache()

                if not user_cache.is_loaded:
                    api.abort(503, "用户缓存未加载，请先加载用户缓存")

                results = user_cache.search_users(query, limit)

                return {
                    "query": query,
                    "results": results,
                    "total": len(results),
                    "limit": limit,
                    "timestamp": datetime.now().isoformat()
                }

            except ValueError as e:
                api.abort(400, f"参数错误: {str(e)}")
            except Exception as e:
                logger.error(f"搜索用户失败: {e}")
                api.abort(500, str(e))

    @cache_ns.route('/validate-mention')
    class MentionValidate(Resource):
        @cache_ns.doc('validate_mention')
        @cache_ns.expect(models['mention_validate_request'])
        @cache_ns.marshal_with(models['mention_validate_response'])
        @cache_ns.response(400, 'Bad Request', models['error_response'])
        @cache_ns.response(503, 'Service Unavailable', models['error_response'])
        @cache_ns.response(500, 'Internal Server Error', models['error_response'])
        def post(self):
            """验证@艾特是否有效"""
            try:
                data = request.get_json()

                if not data:
                    api.abort(400, "请求数据为空")

                mention_name = data.get('mention_name', '').strip()
                chatroom_id = data.get('chatroom_id')

                if not mention_name:
                    api.abort(400, "缺少mention_name参数")

                # 获取用户缓存
                from core.user_cache import get_user_cache
                user_cache = get_user_cache()

                if not user_cache.is_loaded:
                    api.abort(503, "用户缓存未加载，请先加载用户缓存")

                is_valid = user_cache.is_valid_mention(mention_name, chatroom_id)

                return {
                    "mention_name": mention_name,
                    "chatroom_id": chatroom_id,
                    "is_valid": is_valid,
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"验证@艾特失败: {e}")
                api.abort(500, str(e))

    # 预加载管理接口
    @preload_ns.route('/status')
    class PreloadStatusAll(Resource):
        @preload_ns.doc('get_preload_status_all')
        @preload_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self):
            """获取所有预加载状态"""
            try:
                status = preload_manager.get_preload_status()

                return {
                    "preload_status": status,
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"获取预加载状态失败: {e}")
                api.abort(500, str(e))

    @preload_ns.route('/reload-all')
    class PreloadReloadAll(Resource):
        @preload_ns.doc('reload_all_preload')
        @preload_ns.response(500, 'Internal Server Error', models['error_response'])
        def post(self):
            """重新加载所有预加载资源"""
            try:
                result = preload_manager.preload_all()

                return {
                    "message": "重新加载所有预加载资源",
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"重新加载预加载资源失败: {e}")
                api.abort(500, str(e))

    # 聊天记录代理接口
    @proxy_ns.route('/<path:path>')
    class ChatlogProxy(Resource):
        @proxy_ns.doc('proxy_chatlog')
        @proxy_ns.response(503, 'Service Unavailable', models['error_response'])
        @proxy_ns.response(504, 'Gateway Timeout', models['error_response'])
        @proxy_ns.response(500, 'Internal Server Error', models['error_response'])
        def get(self, path):
            """代理聊天记录GET请求"""
            return self._proxy_request(path, 'GET')

        def post(self, path):
            """代理聊天记录POST请求"""
            return self._proxy_request(path, 'POST')

        def put(self, path):
            """代理聊天记录PUT请求"""
            return self._proxy_request(path, 'PUT')

        def delete(self, path):
            """代理聊天记录DELETE请求"""
            return self._proxy_request(path, 'DELETE')

        def patch(self, path):
            """代理聊天记录PATCH请求"""
            return self._proxy_request(path, 'PATCH')

        def _proxy_request(self, path, method):
            """执行代理请求"""
            try:
                # 构建目标URL
                target_url = f"http://127.0.0.1:5030/{path}"

                # 转发查询参数
                if request.args:
                    target_url += '?' + '&'.join([f"{k}={v}" for k, v in request.args.items()])

                # 调试日志
                logger.info(f"代理请求: {method} {request.url} -> {target_url}")

                # 准备请求数据
                headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'content-length']}

                # 根据请求方法转发
                if method == 'GET':
                    response = requests.get(target_url, headers=headers, timeout=30)
                elif method == 'POST':
                    response = requests.post(target_url, json=request.get_json(), headers=headers, timeout=30)
                elif method == 'PUT':
                    response = requests.put(target_url, json=request.get_json(), headers=headers, timeout=30)
                elif method == 'DELETE':
                    response = requests.delete(target_url, headers=headers, timeout=30)
                elif method == 'PATCH':
                    response = requests.patch(target_url, json=request.get_json(), headers=headers, timeout=30)

                # 返回响应
                return response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text, response.status_code

            except requests.exceptions.ConnectionError:
                api.abort(503, "无法连接到聊天记录服务 (127.0.0.1:5030)")
            except requests.exceptions.Timeout:
                api.abort(504, "请求超时")
            except Exception as e:
                logger.error(f"代理请求失败: {e}")
                api.abort(500, f"代理请求失败: {str(e)}")

    return api
