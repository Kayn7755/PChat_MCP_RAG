"""
LLM 抽象层（Abstract LLM Interface），它定义了所有大模型供应商必须遵守的统一接口。
    BaseLLM：规定 LLM应该提供什么能力
    OpenAILLM / AzureLLM / OllamaLLM：具体实现
    LLMFactory：根据配置创建具体实现

Abstract base class for LLM providers.
This module defines the pluggable interface for Language Model providers,
enabling seamless switching between different backends (OpenAI, Azure, Ollama, etc.)
through configuration-driven instantiation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
# ABC(Abstract Base Class) 抽象基类
# 继承后表示该类不能直接使用，而是作为模板

# abstractmethod 抽象方法
# @abstractmethod 继承它的类必须实现。
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# 表示一次聊天消息。对应 OpenAI Chat API：
# {
#  "role":"user",
#  "content":"你好"
# }
@dataclass
class Message:
    """Represents a single message in a chat conversation.
    
    Attributes:
        role: The role of the message sender ('system', 'user', or 'assistant').
        content: The text content of the message.
    """
    role: str
    content: str

# LLM返回结果的数据结构
@dataclass
class ChatResponse:
    """Response from an LLM chat completion.
    
    Attributes:
        content: The generated text response.
        model: The model identifier that generated the response.
        usage: Optional token usage statistics (prompt_tokens, completion_tokens, total_tokens).
        raw_response: Optional raw response from the provider for debugging.
    """
    content: str # 模型回答
    model: str
    usage: Optional[Dict[str, int]] = None # token统计
    raw_response: Optional[Any] = None # 保存原始返回
    # 例如模型返回值为: 
    # response={
    #     id:"xxx",
    #     choices:[...],
    #     content:[...],
    #     usage:{...}
    # }
    # usage等字段只保留部分返回值, 此处保留完整返回值

# 所有LLM必须继承它
class BaseLLM(ABC):
    """Abstract base class for LLM providers.
    
    All LLM implementations must inherit from this class and implement
    the chat() method. This ensures consistent interface across different
    providers (OpenAI, Azure, DeepSeek, Ollama, etc.).
    
    Design Principles Applied:
    - Pluggable: Subclasses can be swapped without changing upstream code.
    - Observable: Accepts optional TraceContext for observability integration.
    - Config-Driven: Instances are created via factory based on settings.
    """
    
    # 核心接口
    @abstractmethod
    def chat(
        self,
        messages: List[Message], # 聊天历史
        trace: Optional[Any] = None, # 用于链路追踪
        **kwargs: Any, # 其它额外参数。
    ) -> ChatResponse:
        """Generate a chat completion response.
        
        Args:
            messages: List of conversation messages (role + content).
            trace: Optional TraceContext for observability (reserved for Stage F).
            **kwargs: Provider-specific parameters (temperature, max_tokens, etc.).
        
        Returns:
            ChatResponse containing the generated text and metadata.
        
        Raises:
            ValueError: If messages list is empty or malformed.
            RuntimeError: If the LLM provider call fails.
        """
        pass # BaseLLM不知道具体怎么调用
        # 不同模型(openai, ollama等)对chat的调用方法不同, 所以此处只规定必须有chat方法
    
    # 检查发送给LLM的消息是否合法
    def validate_messages(self, messages: List[Message]) -> None:
        """Validate message list structure.
        
        Args:
            messages: List of messages to validate.
        
        Raises:
            ValueError: If messages list is empty or contains invalid roles.
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")
        
        valid_roles = {"system", "user", "assistant"}
        for i, msg in enumerate(messages):
            if not isinstance(msg, Message):
                raise ValueError(f"Message at index {i} is not a Message instance")
            if msg.role not in valid_roles:
                raise ValueError(
                    f"Message at index {i} has invalid role '{msg.role}'. "
                    f"Must be one of: {valid_roles}"
                )
            if not msg.content or not msg.content.strip():
                raise ValueError(f"Message at index {i} has empty content")
