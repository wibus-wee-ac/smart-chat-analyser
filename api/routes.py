"""
API路由定义
包含所有REST API端点
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import requests

logger = logging.getLogger(__name__)

def create_api_routes(services):
    """创建API路由蓝图"""
    api = Blueprint('api', __name__, url_prefix='/api/v1')
    
    task_queue = services['task_queue']
    model_manager = services['model_manager']
    analysis_service = services['analysis_service']
    preprocessing_service = services['preprocessing_service']
    visualization_service = services['visualization_service']

    # 代理路由 - 将 /chatlog/* 转发到 http://127.0.0.1:5030/*
    @api.route('/chatlog/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def proxy_chatlog(path):
        """代理聊天记录相关请求到本地服务"""
        try:
            # 构建目标URL - 直接转发路径
            target_url = f"http://127.0.0.1:5030/{path}"

            # 转发查询参数
            if request.args:
                target_url += '?' + '&'.join([f"{k}={v}" for k, v in request.args.items()])

            # 调试日志
            logger.info(f"代理请求: {request.method} {request.url} -> {target_url}")

            # 准备请求数据
            headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'content-length']}

            # 根据请求方法转发
            if request.method == 'GET':
                response = requests.get(target_url, headers=headers, timeout=30)
            elif request.method == 'POST':
                response = requests.post(target_url, json=request.get_json(), headers=headers, timeout=30)
            elif request.method == 'PUT':
                response = requests.put(target_url, json=request.get_json(), headers=headers, timeout=30)
            elif request.method == 'DELETE':
                response = requests.delete(target_url, headers=headers, timeout=30)
            elif request.method == 'PATCH':
                response = requests.patch(target_url, json=request.get_json(), headers=headers, timeout=30)

            # 返回响应
            return response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text, response.status_code

        except requests.exceptions.ConnectionError:
            return jsonify({"error": "无法连接到聊天记录服务 (127.0.0.1:5030)"}), 503
        except requests.exceptions.Timeout:
            return jsonify({"error": "请求超时"}), 504
        except Exception as e:
            logger.error(f"代理请求失败: {e}")
            return jsonify({"error": f"代理请求失败: {str(e)}"}), 500

    @api.route('/health', methods=['GET'])
    def health_check():
        """健康检查"""
        return jsonify({
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
        })
    
    # 任务管理API
    @api.route('/tasks', methods=['GET'])
    def get_tasks():
        """获取任务列表"""
        try:
            # 获取查询参数
            status_filter = request.args.get('status')
            limit = int(request.args.get('limit', 20))  # 默认返回20个任务
            offset = int(request.args.get('offset', 0))  # 默认偏移量为0

            # 参数验证
            if limit > 100:  # 限制最大返回数量
                limit = 100
            if limit < 1:
                limit = 1
            if offset < 0:
                offset = 0

            # 验证状态过滤器
            valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
            if status_filter and status_filter not in valid_statuses:
                return jsonify({
                    "error": f"无效的状态过滤器，支持的状态: {', '.join(valid_statuses)}"
                }), 400

            # 获取任务列表
            tasks = task_queue.get_all_tasks(status_filter, limit, offset)
            total_count = task_queue.get_task_count(status_filter)

            # 转换为字典格式（不包含result字段以减少传输数据量）
            task_list = [task.to_dict(include_result=False) for task in tasks]

            return jsonify({
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
            })

        except ValueError as e:
            return jsonify({"error": f"参数错误: {str(e)}"}), 400
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route('/tasks', methods=['POST'])
    def submit_task():
        """提交分析任务"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "请求数据为空"}), 400
            
            # 设置默认任务类型
            task_type = data.get('task_type', 'chatlog_analysis')
            task_data = data.get('task_data', {})
            
            # 验证必要参数
            if task_type == 'chatlog_analysis':
                if not task_data.get('talker') and not task_data.get('limit'):
                    return jsonify({
                        "error": "聊天记录分析任务需要提供 talker 或 limit 参数"
                    }), 400
            
            # 提交任务
            task_id = task_queue.submit_task(task_type, task_data)
            
            return jsonify({
                "task_id": task_id,
                "status": "submitted",
                "message": "任务已提交",
                "task_type": task_type,
                "submitted_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"提交任务失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    @api.route('/tasks/<task_id>', methods=['GET'])
    def get_task_status(task_id: str):
        """获取任务状态"""
        try:
            task_info = task_queue.get_task_status(task_id)
            
            if not task_info:
                return jsonify({"error": "任务不存在"}), 404
            
            return jsonify(task_info.to_dict())
            
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    @api.route('/tasks/<task_id>/result', methods=['GET'])
    def get_task_result(task_id: str):
        """获取任务结果"""
        try:
            task_info = task_queue.get_task_status(task_id)
            
            if not task_info:
                return jsonify({"error": "任务不存在"}), 404
            
            from core.task_queue import TaskStatus
            if task_info.status != TaskStatus.COMPLETED:
                return jsonify({
                    "error": "任务尚未完成",
                    "status": task_info.status.value,
                    "progress": task_info.progress,
                    "message": task_info.message
                }), 400
            
            return jsonify({
                "task_id": task_id,
                "status": task_info.status.value,
                "result": task_info.result,
                "completed_at": task_info.completed_at.isoformat() if task_info.completed_at else None
            })
            
        except Exception as e:
            logger.error(f"获取任务结果失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    @api.route('/tasks/<task_id>/cancel', methods=['POST'])
    def cancel_task(task_id: str):
        """取消任务"""
        try:
            task_info = task_queue.get_task_status(task_id)
            
            if not task_info:
                return jsonify({"error": "任务不存在"}), 404
            
            from core.task_queue import TaskStatus
            if task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return jsonify({
                    "error": "任务已完成，无法取消",
                    "status": task_info.status.value
                }), 400
            
            # 更新任务状态为已取消
            task_info.status = TaskStatus.CANCELLED
            task_info.completed_at = datetime.now()
            task_info.message = "任务已被用户取消"
            task_queue._save_task_info(task_info)
            
            return jsonify({
                "task_id": task_id,
                "status": "cancelled",
                "message": "任务已取消"
            })
            
        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    # 队列和系统状态API
    @api.route('/queue/stats', methods=['GET'])
    def get_queue_stats():
        """获取队列统计信息"""
        try:
            stats = task_queue.get_queue_stats()
            model_info = model_manager.get_model_info()
            
            return jsonify({
                "queue": stats,
                "models": model_info,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"获取队列统计失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    @api.route('/system/stats', methods=['GET'])
    def get_system_stats():
        """获取系统统计信息"""
        try:
            return jsonify({
                "task_queue": task_queue.get_queue_stats(),
                "model_manager": model_manager.get_model_info(),
                "analysis_service": analysis_service.get_service_stats(),
                "preprocessing_service": preprocessing_service.get_preprocessing_stats(),
                "visualization_service": visualization_service.get_service_stats(),
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    # 分析器管理API
    @api.route('/analyzers', methods=['GET'])
    def get_analyzers():
        """获取可用分析器列表"""
        try:
            analyzers = analysis_service.get_available_analyzers()
            analyzer_info = {}
            
            for analyzer_name in analyzers:
                try:
                    analyzer_info[analyzer_name] = analysis_service.get_analyzer_info(analyzer_name)
                except Exception as e:
                    analyzer_info[analyzer_name] = {"error": str(e)}
            
            return jsonify({
                "analyzers": analyzers,
                "analyzer_info": analyzer_info,
                "total_count": len(analyzers)
            })
            
        except Exception as e:
            logger.error(f"获取分析器列表失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    @api.route('/analyzers/<analyzer_name>', methods=['GET'])
    def get_analyzer_info(analyzer_name: str):
        """获取特定分析器信息"""
        try:
            info = analysis_service.get_analyzer_info(analyzer_name)
            return jsonify(info)
            
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logger.error(f"获取分析器信息失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    # 模型管理API
    @api.route('/models/info', methods=['GET'])
    def get_model_info():
        """获取模型信息"""
        try:
            info = model_manager.get_model_info()
            return jsonify(info)
            
        except Exception as e:
            logger.error(f"获取模型信息失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    @api.route('/models/clear', methods=['POST'])
    def clear_models():
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

            return jsonify({
                "message": message,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"清除模型失败: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route('/models/preload', methods=['POST'])
    def preload_models():
        """预加载模型"""
        try:
            data = request.get_json() or {}
            model_key = data.get('model_key')
            force = data.get('force', False)

            if model_key:
                # 预加载指定模型
                success = model_manager.preload_model(model_key, force=force)
                if success:
                    return jsonify({
                        "message": f"开始预加载模型: {model_key}",
                        "model_key": model_key,
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    return jsonify({"error": f"无法预加载模型: {model_key}"}), 400
            else:
                # 预加载所有模型
                results = model_manager.preload_all_models(force=force)
                return jsonify({
                    "message": "开始批量预加载模型",
                    "results": results,
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"预加载模型失败: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route('/models/preload/status', methods=['GET'])
    def get_preload_status():
        """获取预加载状态"""
        try:
            model_key = request.args.get('model_key')
            status = model_manager.get_preload_status(model_key)

            return jsonify({
                "status": status,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"获取预加载状态失败: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route('/models/preload/cancel', methods=['POST'])
    def cancel_preload():
        """取消预加载任务"""
        try:
            data = request.get_json() or {}
            model_key = data.get('model_key')

            if not model_key:
                return jsonify({"error": "缺少model_key参数"}), 400

            success = model_manager.cancel_preload(model_key)

            if success:
                return jsonify({
                    "message": f"已取消模型预加载: {model_key}",
                    "model_key": model_key,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return jsonify({
                    "message": f"无法取消模型预加载: {model_key}",
                    "model_key": model_key,
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"取消预加载失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    # 错误处理
    @api.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "接口不存在"}), 404
    
    @api.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "服务器内部错误"}), 500
    
    @api.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "请求参数错误"}), 400
    
    return api
