"""
日志工具模块 - 用于记录API请求和响应信息
"""
import logging
import json
from datetime import datetime
from typing import Any, Dict


class RequestLogger:
    """API请求日志记录器"""
    
    def __init__(self):
        """初始化日志配置"""
        # 创建自定义logger
        self.logger = logging.getLogger('API_REQUEST')
        
        # 如果logger还没有handler，添加handler
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            
            # 创建控制台handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # 设置简洁的日志格式
            formatter = logging.Formatter('%(message)s')
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
        
        # 存储最后一次请求的信息（用于在结束时添加到同一行）
        self._last_request_info = None
    
    def log_request_start(self, method: str, path: str, query_params: Dict = None, body: Any = None):
        """
        记录请求开始信息
        
        Args:
            method: HTTP方法 (GET, POST, PUT, DELETE等)
            path: 请求路径
            query_params: 查询参数
            body: 请求体
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 输出空行分隔
        self.logger.info('')
        
        # 构建请求行
        request_line = f"[{timestamp}] {method} {path}"
        
        # 存储请求信息（使用局部变量，避免实例属性）
        last_request_info = {
            'timestamp': timestamp,
            'method': method,
            'path': path,
            'query_params': query_params,
            'body': body
        }
        
        # 输出请求信息
        self.logger.info(request_line)
        
        # 查询参数/请求体
        if query_params:
            params_str = json.dumps(query_params, ensure_ascii=False)
            self.logger.info(f"RequestBody: {params_str}")
        
        # 输出请求体
        if body:
            body_str = json.dumps(body, ensure_ascii=False, indent=2) if isinstance(body, dict) else str(body)
            self.logger.info(f"{body_str}")
        
        # 将请求信息保存到类属性，供 log_request_end 使用
        self._last_request_info = last_request_info
    
    def log_request_end(self, method: str, path: str, status_code: int, process_time: float, response_data: Any = None):
        """
        记录请求结束信息
        
        Args:
            method: HTTP方法
            path: 请求路径
            status_code: 响应状态码
            process_time: 处理时间（秒）
            response_data: 响应数据
        """
        # 转换时间为毫秒
        process_time_ms = process_time * 1000
        
        # 重新输出请求行，并在末尾添加响应状态和耗时
        if self._last_request_info:
            timestamp = self._last_request_info['timestamp']
            request_method = self._last_request_info['method']
            request_path = self._last_request_info['path']
            query_params = self._last_request_info.get('query_params')
            body = self._last_request_info.get('body')
            
            # 清除旧信息
            self._last_request_info = None
            
            # 输出空行分隔
            self.logger.info('')
            
            # 构建完整的请求行（末尾包含响应状态）
            request_line = f"[{timestamp}] {request_method} {request_path}"
            
            # 查询参数/请求体
            if query_params:
                params_str = json.dumps(query_params, ensure_ascii=False)
                request_line += f" RequestBody: {params_str}"
            
            # 请求体
            if body:
                body_str = json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else str(body)
                request_line += f" {body_str}"
            
            # 添加响应状态和耗时
            request_line += f" -> {status_code} ({process_time_ms:.0f}ms)"
            
            # 输出完整行
            self.logger.info(request_line)
        else:
            # 如果没有请求信息，只输出响应状态
            self.logger.info(f"-> {status_code} ({process_time_ms:.0f}ms)")
        
        # 响应数据（格式化输出）
        if response_data:
            response_str = json.dumps(response_data, ensure_ascii=False, indent=2)
            # 如果响应太长，截断显示
            if len(response_str) > 500:
                response_str = response_str[:500] + '\n...'
            self.logger.info(f"{response_str}")


# 创建全局日志记录器实例
api_logger = RequestLogger()
