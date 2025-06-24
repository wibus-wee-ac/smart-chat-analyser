"""
API数据模型定义
用于Flask-RESTX的请求和响应模型
"""

from flask_restx import fields

def create_api_models(api):
    """创建所有API模型"""
    
    # 基础响应模型
    base_response = api.model('BaseResponse', {
        'timestamp': fields.String(description='响应时间戳', example='2024-01-01T12:00:00'),
    })
    
    error_response = api.model('ErrorResponse', {
        'error': fields.String(required=True, description='错误信息', example='参数错误'),
        'timestamp': fields.String(description='错误时间戳', example='2024-01-01T12:00:00'),
    })
    
    # 健康检查模型
    service_status = api.model('ServiceStatus', {
        'task_queue': fields.Boolean(description='任务队列状态'),
        'model_manager': fields.Boolean(description='模型管理器状态'),
        'preprocessing_service': fields.Boolean(description='预处理服务状态'),
        'analysis_service': fields.Boolean(description='分析服务状态'),
        'visualization_service': fields.Boolean(description='可视化服务状态'),
    })
    
    health_response = api.model('HealthResponse', {
        'status': fields.String(required=True, description='健康状态', example='healthy'),
        'timestamp': fields.String(required=True, description='检查时间'),
        'version': fields.String(required=True, description='版本号', example='1.0.0'),
        'services': fields.Nested(service_status, description='服务状态'),
    })
    
    # 任务相关模型
    task_data = api.model('TaskData', {
        'talker': fields.String(description='分析的用户名'),
        'limit': fields.Integer(description='分析消息数量限制'),
        'chatroom_id': fields.String(description='聊天室ID'),
    })
    
    task_request = api.model('TaskRequest', {
        'task_type': fields.String(required=True, description='任务类型', example='chatlog_analysis'),
        'task_data': fields.Nested(task_data, description='任务数据'),
    })
    
    task_submit_response = api.model('TaskSubmitResponse', {
        'task_id': fields.String(required=True, description='任务ID'),
        'status': fields.String(required=True, description='提交状态', example='submitted'),
        'message': fields.String(required=True, description='提交消息'),
        'task_type': fields.String(required=True, description='任务类型'),
        'submitted_at': fields.String(required=True, description='提交时间'),
        'chat_name': fields.String(description='群聊名称'),
    })
    
    pagination_info = api.model('PaginationInfo', {
        'total': fields.Integer(required=True, description='总数量'),
        'limit': fields.Integer(required=True, description='每页限制'),
        'offset': fields.Integer(required=True, description='偏移量'),
        'has_more': fields.Boolean(required=True, description='是否有更多数据'),
    })
    
    task_filters = api.model('TaskFilters', {
        'status': fields.String(description='状态过滤器'),
    })
    
    task_info = api.model('TaskInfo', {
        'task_id': fields.String(required=True, description='任务ID'),
        'task_type': fields.String(required=True, description='任务类型'),
        'status': fields.String(required=True, description='任务状态'),
        'progress': fields.Float(description='任务进度 (0-1)'),
        'message': fields.String(description='任务消息'),
        'created_at': fields.String(description='创建时间'),
        'started_at': fields.String(description='开始时间'),
        'completed_at': fields.String(description='完成时间'),
        'chat_name': fields.String(description='群聊名称'),
    })
    
    tasks_list_response = api.model('TasksListResponse', {
        'tasks': fields.List(fields.Nested(task_info), required=True, description='任务列表'),
        'pagination': fields.Nested(pagination_info, required=True, description='分页信息'),
        'filters': fields.Nested(task_filters, description='过滤器信息'),
        'timestamp': fields.String(required=True, description='响应时间'),
    })
    
    task_result_response = api.model('TaskResultResponse', {
        'task_id': fields.String(required=True, description='任务ID'),
        'status': fields.String(required=True, description='任务状态'),
        'result': fields.Raw(description='任务结果数据'),
        'completed_at': fields.String(description='完成时间'),
        'chat_name': fields.String(description='群聊名称'),
    })
    
    task_cancel_response = api.model('TaskCancelResponse', {
        'task_id': fields.String(required=True, description='任务ID'),
        'status': fields.String(required=True, description='取消状态'),
        'message': fields.String(required=True, description='取消消息'),
    })
    
    # 队列统计模型
    queue_stats = api.model('QueueStats', {
        'pending': fields.Integer(description='等待中的任务数'),
        'running': fields.Integer(description='运行中的任务数'),
        'completed': fields.Integer(description='已完成的任务数'),
        'failed': fields.Integer(description='失败的任务数'),
        'cancelled': fields.Integer(description='已取消的任务数'),
    })
    
    model_info = api.model('ModelInfo', {
        'loaded_models': fields.List(fields.String, description='已加载的模型'),
        'model_status': fields.Raw(description='模型状态信息'),
    })
    
    queue_stats_response = api.model('QueueStatsResponse', {
        'queue': fields.Nested(queue_stats, description='队列统计'),
        'models': fields.Nested(model_info, description='模型信息'),
        'timestamp': fields.String(required=True, description='统计时间'),
    })
    
    # 分析器模型
    analyzer_info = api.model('AnalyzerInfo', {
        'name': fields.String(description='分析器名称'),
        'description': fields.String(description='分析器描述'),
        'version': fields.String(description='版本号'),
        'parameters': fields.Raw(description='参数信息'),
    })
    
    analyzers_response = api.model('AnalyzersResponse', {
        'analyzers': fields.List(fields.String, required=True, description='可用分析器列表'),
        'analyzer_info': fields.Raw(description='分析器详细信息'),
        'total_count': fields.Integer(required=True, description='分析器总数'),
    })
    
    # 模型管理模型
    model_clear_request = api.model('ModelClearRequest', {
        'model_key': fields.String(description='要清除的模型键名'),
    })
    
    model_preload_request = api.model('ModelPreloadRequest', {
        'model_key': fields.String(description='要预加载的模型键名'),
        'force': fields.Boolean(description='是否强制重新加载', default=False),
    })
    
    # 用户缓存模型
    user_search_result = api.model('UserSearchResult', {
        'user_id': fields.String(description='用户ID'),
        'display_name': fields.String(description='显示名称'),
        'mention_name': fields.String(description='@艾特名称'),
        'chatroom_ids': fields.List(fields.String, description='所在聊天室ID列表'),
    })
    
    user_search_response = api.model('UserSearchResponse', {
        'query': fields.String(required=True, description='搜索关键词'),
        'results': fields.List(fields.Nested(user_search_result), description='搜索结果'),
        'total': fields.Integer(required=True, description='结果总数'),
        'limit': fields.Integer(required=True, description='限制数量'),
        'timestamp': fields.String(required=True, description='搜索时间'),
    })
    
    mention_validate_request = api.model('MentionValidateRequest', {
        'mention_name': fields.String(required=True, description='@艾特名称'),
        'chatroom_id': fields.String(description='聊天室ID'),
    })
    
    mention_validate_response = api.model('MentionValidateResponse', {
        'mention_name': fields.String(required=True, description='@艾特名称'),
        'chatroom_id': fields.String(description='聊天室ID'),
        'is_valid': fields.Boolean(required=True, description='是否有效'),
        'timestamp': fields.String(required=True, description='验证时间'),
    })
    
    return {
        'base_response': base_response,
        'error_response': error_response,
        'health_response': health_response,
        'task_request': task_request,
        'task_submit_response': task_submit_response,
        'tasks_list_response': tasks_list_response,
        'task_result_response': task_result_response,
        'task_cancel_response': task_cancel_response,
        'queue_stats_response': queue_stats_response,
        'analyzers_response': analyzers_response,
        'analyzer_info': analyzer_info,
        'model_clear_request': model_clear_request,
        'model_preload_request': model_preload_request,
        'user_search_response': user_search_response,
        'mention_validate_request': mention_validate_request,
        'mention_validate_response': mention_validate_response,
    }
