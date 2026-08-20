"""
按模型名查找对应的 API 地址、密钥和模型 ID,供上层调用不同 LLM
"""

from __future__ import annotations

from dataclasses import dataclass
@dataclass(frozen=True) # @dataclass：让这个类自动生成常用方法（如 __init__, __repr__, __eq__）
# frozen=True：把实例设为“只读不可变对象”
class ModelEndpoint: # 模型端点类，包含 base_url、api_key、model。
    """OpenAI 兼容 Chat Completions 端点。"""
    base_url: str
    api_key: str
    model: str

# 一个“字典封装器”，负责按模型 key 找到对应 url、api
# OpenAI-Compatible API 对应的是：用 OpenAI 的 /chat/completions 请求格式去调各类大模型（DeepSeek / 智谱 / 通义等），而不是官方 OpenAI SDK。
class ChatClientRegistry:
    """按模型键（如 deepseek-chat、glm-4.6、qwen3-max）解析端点。"""

    def __init__(self, clients: dict[str, ModelEndpoint]) -> None:
        self._clients = dict(clients)

    def get(self, key: str) -> ModelEndpoint | None:
        return self._clients.get(key)

    def register(self, key: str, endpoint: ModelEndpoint) -> None:
        self._clients[key] = endpoint

# 从环境变量自动创建一个默认的模型注册表。初始化默认的模型 url、api、key
def default_registry_from_env() -> ChatClientRegistry:
    import os

    m: dict[str, ModelEndpoint] = {}
    ds_key = os.environ.get("JCHATMIND_DEEPSEEK_API_KEY", "")
    if ds_key:
        m["deepseek-chat"] = ModelEndpoint(
            base_url=os.environ.get("JCHATMIND_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=ds_key,
            model=os.environ.get("JCHATMIND_DEEPSEEK_MODEL", "deepseek-chat"),
        )
    zp_key = os.environ.get("JCHATMIND_ZHIPU_API_KEY", "")
    if zp_key:
        m["glm-4.6"] = ModelEndpoint(
            base_url=os.environ.get("JCHATMIND_ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
            api_key=zp_key,
            model=os.environ.get("JCHATMIND_ZHIPU_MODEL", "glm-4.6"),
        )
    qw_key = os.environ.get("JCHATMIND_QWEN_API_KEY", "")
    if qw_key:
        m["qwen3-max"] = ModelEndpoint(
            base_url=os.environ.get(
                "JCHATMIND_QWEN_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            api_key=qw_key,
            model=os.environ.get("JCHATMIND_QWEN_MODEL", "qwen3-max"),
        )
    return ChatClientRegistry(m)
# 启动时的“自动装配配置”函数：
# 哪些模型能用，取决于对应 API Key 是否在环境变量里配置好了。