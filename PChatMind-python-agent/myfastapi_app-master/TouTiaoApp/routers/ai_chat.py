"""
连接AI模型可以直接写在前端, 由浏览器 → DeepSeek, 但是API Key会暴露在浏览器
此处用后端的 AI 代理接口, 浏览器 → 你的后端 → DeepSeek

该文件作用: 
保管 API Key — Key 在 ai_conf.py，前端看不到、不会泄露
转发请求 — 收到 message / history / stream，拼好后用 httpx 调 DeepSeek
两种返回方式
stream=true → SSE 流式推给前端
stream=false → 普通 JSON（reply + usage）
简单校验 — Key 是否配置、消息是否为空、错误统一包装
"""

# 导入异步 HTTP 客户端库
import httpx
# 导入 FastAPI 路由和依赖注入相关类
from fastapi import APIRouter
# 导入流式响应
from fastapi.responses import StreamingResponse
# 导入 Pydantic 模型基类，用于数据验证
from pydantic import BaseModel
# 导入全局响应封装工具
from TouTiaoApp.utils.response import success_response, fail_response
# 导入 AI 配置文件
from TouTiaoApp.config.ai_conf import AI_CHAT_CONFIG

# 创建 AI 路由实例
router = APIRouter(prefix="/api/ai", tags=["AI问答"])


# 定义聊天请求的数据模型
class ChatRequest(BaseModel):
    """AI 聊天请求模型"""
    message: str
    history: list = []
    # 控制是否使用流式输出，默认为 False（非流式）
    stream: bool = False # 只有 AI 问答的流式输出用了 SSE，不是整站都靠 SSE 推送
    # 其它接口（新闻、登录、收藏、历史）都是普通 HTTP 请求 → JSON 响应，没有用 SSE/WebSocket 做服务端主动推送。


@router.post("/chat", summary="AI 智能问答")
async def ai_chat(request: ChatRequest):
    """
    AI 问答接口（支持流式与非流式）
    """
    if not AI_CHAT_CONFIG.get("api_key"):
        return fail_response(code=500, msg="API Key 未配置")

    if not request.message.strip():
        return fail_response(code=400, msg="消息内容不能为空")

    try:
        messages = request.history + [{"role": "user", "content": request.message}]

        # 构建请求体，动态使用前端传来的 stream 参数
        payload = {
            "model": AI_CHAT_CONFIG["model"],
            "messages": messages,
            "stream": request.stream,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_CHAT_CONFIG['api_key']}",
        }

        # ==========================================
        # 分支 1：流式响应 (SSE) 逻辑
        # ==========================================
        if request.stream:
            async def event_generator():
                async with httpx.AsyncClient() as gen_client:
                    async with gen_client.stream(
                            "POST",
                            AI_CHAT_CONFIG["api_endpoint"],
                            headers=headers,
                            json=payload,
                            timeout=AI_CHAT_CONFIG.get("timeout", 60.0)
                    ) as gen_response:
                        if gen_response.status_code != 200:
                            error_data = await gen_response.aread()
                            yield f"data: AI 服务调用失败: {error_data.decode()}\n\n"
                            return

                        async for chunk in gen_response.aiter_text():
                            if chunk:
                                yield chunk

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )

        # ==========================================
        # 分支 2：非流式响应 (普通 JSON) 逻辑
        # ==========================================
        else:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    AI_CHAT_CONFIG["api_endpoint"],
                    headers=headers,
                    json=payload,
                    timeout=AI_CHAT_CONFIG.get("timeout", 60.0)
                )

                if response.status_code != 200:
                    return fail_response(code=500, msg=f"AI 服务调用失败: {response.text}")

                resp_data = response.json()

                reply_text = ""
                if "choices" in resp_data and len(resp_data["choices"]) > 0:
                    reply_text = resp_data["choices"][0].get("message", {}).get("content", "")

                return success_response(data={
                    "reply": reply_text,
                    "usage": resp_data.get("usage", {})
                })

    except Exception as e:
        return fail_response(code=500, msg=f"AI 服务异常: {str(e)}")