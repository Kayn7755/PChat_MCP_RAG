# 导入FastAPI核心类，用于创建Web应用
from fastapi import FastAPI, Request
# 导入CORS中间件，用于处理跨域请求
from fastapi.middleware.cors import CORSMiddleware
# 导入starlette响应类
from starlette.responses import Response, StreamingResponse
# 导入新闻和用户路由模块，定义API端点
from TouTiaoApp.routers import news, users, favorite, history, ai_chat
# 导入全局异常处理器注册函数
from TouTiaoApp.utils.exception import register_exceptions
# 导入日志工具
from TouTiaoApp.utils.log_utils import api_logger
from typing import Mapping
import json
import time

# 创建FastAPI应用实例，作为整个应用的入口
app = FastAPI()

# 真实上线后允许的ip地址
origin = [
    "http://localhost",
    "http://localhost:3000",
    "http://192.168.1:145"
]

# 配置CORS（跨域资源共享）中间件
app.add_middleware(
    CORSMiddleware,
    # 允许的来源列表，"*"表示允许所有来源（仅开发环境使用）
    allow_origins=["*"],
    # 是否允许携带凭证（如cookies、authorization headers）
    allow_credentials=True,
    # 允许的HTTP方法列表，"*"表示允许所有方法（GET、POST等）
    allow_methods=["*"],
    # 允许的请求头列表，"*"表示允许所有请求头
    allow_headers=["*"],
)  # type: ignore[arg-type]


# API请求日志中间件 - 记录请求路径、方法、入参和响应
@app.middleware("http")
async def api_request_logger(request: Request, call_next):
    """记录所有API请求的详细信息"""
    # 忽略 OPTIONS 预检请求（跨域检查）
    if request.method == "OPTIONS":
        return await call_next(request)
    
    # 记录请求开始时间
    start_time = time.time()
    
    # 获取请求信息
    method = request.method
    path = request.url.path
    query_params = dict(request.query_params)
    
    # 尝试读取请求体（不修改原始请求）
    body = None
    if method in ["POST", "PUT", "PATCH"]:
        try:
            body_bytes = await request.body()
            if body_bytes:
                body = json.loads(body_bytes)
        except Exception as e:
            body = f"<无法解析: {str(e)}>"
    
    # 记录请求开始日志
    api_logger.log_request_start(method, path, query_params, body)
    
    # 处理请求
    response = await call_next(request)
    
    # 计算处理时间
    process_time = time.time() - start_time
    
    # 判断是否为流式响应
    content_type = response.headers.get('content-type', '')
    is_streaming = 'text/event-stream' in content_type
    
    if is_streaming:
        # 流式响应：包装响应体以记录实际文本内容
        
        # 收集流式数据的生成器
        async def logging_stream_wrapper():
            chunk_count = 0
            total_chars = 0
            extracted_text_parts = []  # 保存提取的文本内容
            
            # 使用正确的属性名访问流式数据
            stream_gen = getattr(response, 'body_iterator', None)
            if stream_gen is None:
                # 如果 body_iterator 不存在，尝试其他方法
                yield b""
                return
            
            async for stream_chunk in stream_gen:
                chunk_count += 1
                if isinstance(stream_chunk, bytes):
                    chunk_text = stream_chunk.decode('utf-8', errors='ignore')
                else:
                    chunk_text = str(stream_chunk)
                
                total_chars += len(chunk_text)
                
                # 解析SSE数据，提取实际文本内容
                lines = chunk_text.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data_str = line[6:]  # 去掉 "data: " 前缀
                        if data_str == '[DONE]':
                            continue
                        try:
                            data_json = json.loads(data_str)
                            # 提取 delta.content
                            content = data_json.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                extracted_text_parts.append(content)
                        except json.JSONDecodeError:
                            pass  # 忽略JSON解析错误
                
                yield stream_chunk
            
            # 流式响应结束后记录日志
            full_text = ''.join(extracted_text_parts)
            
            # 构建响应数据
            streaming_response_data: Mapping[str, object] = {
                "_type": "Streaming Response (SSE)",
                "_chunks_sent": chunk_count,
                "_total_chars": total_chars,
                "_extracted_text_length": len(full_text),
            }
            
            # 如果文本不太长，显示完整内容
            if len(full_text) <= 500:
                streaming_response_data = dict(streaming_response_data)  # type: ignore
                streaming_response_data["_content"] = full_text if full_text else "<empty>"
            else:
                # 否则显示前500字符
                streaming_response_data = dict(streaming_response_data)  # type: ignore
                streaming_response_data["_content_preview"] = full_text[:500] + "\n..."
                streaming_response_data["_note"] = "Text truncated, showing first 500 chars"
            
            api_logger.log_request_end(
                method=method,
                path=path,
                status_code=response.status_code,
                process_time=process_time,
                response_data=dict(streaming_response_data)  # type: ignore
            )
        
        # 创建新的流式响应
        new_response = StreamingResponse(
            logging_stream_wrapper(),
            media_type=response.media_type,
            headers=dict(response.headers)
        )
        return new_response
    
    # 普通响应：读取并记录响应体
    try:
        # 获取响应体的字节内容（安全地读取 body_iterator）
        response_body = b""
        
        # 检查 body_iterator 是否存在
        if hasattr(response, 'body_iterator'):
            async for resp_chunk in response.body_iterator:
                response_body += resp_chunk
        elif hasattr(response, 'body'):
            # 备用方案：直接读取 body 属性
            response_body = response.body if isinstance(response.body, bytes) else b""
        
        # 尝试解析 JSON
        response_data: Mapping[str, object] = {}  # type: ignore
        if response_body:
            try:
                response_data = json.loads(response_body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 如果不是 JSON，可能是其他格式
                text_preview = response_body.decode('utf-8', errors='ignore')[:200]
                response_data = {"_type": "Non-JSON response", "_preview": text_preview}
        else:
            # 空响应体
            response_data = {"_note": "Empty response body"}
        
        # 重新构造响应（因为 body_iterator 已被消费）
        new_response = Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )
        response = new_response
        
    except Exception as e:
        # 如果读取失败，记录错误信息
        response_data = {"_error": f"Failed to read response: {str(e)}"}
    
    # 记录请求结束日志
    api_logger.log_request_end(
        method=method,
        path=path,
        status_code=response.status_code,
        process_time=process_time,
        response_data=response_data
    )
    
    return response


# 注册全局异常处理器
register_exceptions(app)

# 定义根路径（/）的GET请求处理函数
@app.get("/")
def read_root():
    # 返回简单的欢迎信息
    return {"Hello": "World"}

# 注册新闻路由到应用中，使/api/news下的端点生效
app.include_router(news.router)
# 注册用户路由到应用中，使/api/user下的端点生效
app.include_router(users.router)
# 注册收藏路由到应用中，使/api/favorite下的端点生效
app.include_router(favorite.router)
# 注册历史记录路由到应用中，使/api/history下的端点生效
app.include_router(history.router)
# 注册AI问答路由到应用中，使/api/ai下的端点生效
app.include_router(ai_chat.router)

# Python程序入口点，仅在直接运行此文件时执行
if __name__ == '__main__':
    # 导入uvicorn ASGI服务器，用于运行FastAPI应用
    import uvicorn
    # 启动uvicorn服务器，监听127.0.0.1:8000
    uvicorn.run(app, host="127.0.0.1", port=8000)