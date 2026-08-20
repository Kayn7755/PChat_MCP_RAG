"""
MCP 的协议中间层：管工具注册、tools/list / tools/call 路由，以及执行时的错误包装。不负责 HybridSearch 本身
管理有哪些 tool、怎么 list/call、怎么把参数交给 handler
MCP Protocol Handler for JSON-RPC 2.0 message handling.

This module provides the ProtocolHandler class that encapsulates:
- Tool registration and schema management
- JSON-RPC error code handling
- Capability negotiation during initialize
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from mcp import types
from mcp.server.lowlevel import Server

from src.observability.logger import get_logger

# MCP 底层通信基于 JSON-RPC
# JSON-RPC 2.0 Error Codes
class JSONRPCErrorCodes:
    """Standard JSON-RPC 2.0 error codes."""

    PARSE_ERROR = -32700 # json解析失败
    INVALID_REQUEST = -32600 # json不合法
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

# 保存一个 MCP Tool 的所有信息
@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""

    name: str
    description: str
    input_schema: Dict[str, Any] # 输入参数, 告诉客户端这个工具需要什么参数
    handler: Callable[..., Any] # query_knowledge_hub_handler

# 核心类, 管理所有 Tool 的信息
# 注册 Tool
# 保存 Tool 信息
# 根据名字执行 Tool
# 返回 MCP 格式结果
@dataclass
class ProtocolHandler:
    """Handles MCP protocol operations including tool registration and execution.

    This class encapsulates:
    - Tool registration with schema validation
    - Tool execution with error handling
    - Capability declaration for initialize response

    Attributes:
        server_name: Name of the MCP server.
        server_version: Version string of the server.
        tools: Registry of available tools.
    """

    server_name: str
    server_version: str
    tools: Dict[str, ToolDefinition] = field(default_factory=dict) # 可用的工具列表

    def __post_init__(self) -> None:
        """Initialize logger after dataclass initialization."""
        self._logger = get_logger(log_level="INFO")

    # 注册 Tool
    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """Register a tool with the protocol handler.

        Args:
            name: Unique name for the tool. 工具名字
            description: Human-readable description of what the tool does. 工具描述
            input_schema: JSON Schema for the tool's input parameters. 工具输入参数
            handler: Async function that executes the tool logic. 工具执行函数

        Raises:
            ValueError: If a tool with the same name is already registered. 如果工具名字已经注册了
        """
        if name in self.tools:
            raise ValueError(f"Tool '{name}' is already registered")

        self.tools[name] = ToolDefinition(
            name=name,
            description=description, # 工具描述
            input_schema=input_schema, # 工具输入参数
            handler=handler, # 工具执行函数
        )
        self._logger.info("Registered tool: %s", name)

    # 获取所有工具的 schema(Tool 的输入参数规范（Input Schema），使用 JSON Schema 描述。)
    # 例: 通过schema告诉客户端query_knowledge_hub 是一个函数，它接收一个 JSON 对象，这个对象里面：query 必须是字符串 top_k 是整数，可选 collection 是字符串，可选
    # TOOL_INPUT_SCHEMA = {
    # "type": "object",
    # "properties": {
    #     "query": {
    #         "type": "string"
    #     },
    #     "top_k": {
    #         "type": "integer"
    #     },
    #     "collection": {
    #         "type": "string"
    #     }
    # },
    # "required": [
    #     "query"
    #     ]
    # }
    def get_tool_schemas(self) -> List[types.Tool]:
        """Get list of tool schemas for tools/list response.

        Returns:
            List of Tool objects with name, description, and inputSchema.
        """
        return [
            types.Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.input_schema,
            )
            for tool in self.tools.values()
        ]

    # 执行工具, 通过传入的工具名找到工具并使用
    async def execute_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> types.CallToolResult:
        """Execute a registered tool by name.

        Args:
            name: Name of the tool to execute.
            arguments: Arguments to pass to the tool handler.

        Returns:
            CallToolResult with content blocks or error indication.

        Raises:
            ValueError: If tool is not found.
        """
        if name not in self.tools:
            self._logger.warning("Tool not found: %s", name)
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error: Tool '{name}' not found",
                    )
                ],
                isError=True,
            )

        tool = self.tools[name]
        try:
            self._logger.info("Executing tool: %s", name)
            result = await tool.handler(**arguments)

            # Handle different return types
            if isinstance(result, types.CallToolResult):
                return result
            if isinstance(result, str):
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=result)],
                    isError=False,
                )
            if isinstance(result, list):
                return types.CallToolResult(content=result, isError=False)
            # Default: convert to string
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=str(result))],
                isError=False,
            )

        except TypeError as e:
            # Invalid parameters
            self._logger.error("Invalid params for tool %s: %s", name, e)
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error: Invalid parameters - {e}",
                    )
                ],
                isError=True,
            )
        except Exception as e:
            # Internal error - don't leak stack trace
            self._logger.exception("Internal error executing tool %s", name)
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Error: Internal server error while executing '{name}'",
                    )
                ],
                isError=True,
            )

    # 获取服务器能力, 用于 initialize 响应
    # 获取工具列表
    def get_capabilities(self) -> Dict[str, Any]:
        """Get server capabilities for initialize response.

        Returns:
            Dictionary of server capabilities.
        """
        return {
            "tools": {} if self.tools else {},
        }

# 注册默认工具
def _register_default_tools(protocol_handler: ProtocolHandler) -> None:
    """Register all default MCP tools with the protocol handler.

    Args:
        protocol_handler: ProtocolHandler instance to register tools with.
    """
    # Import and register query_knowledge_hub tool 导入并注册 query_knowledge_hub 工具
    from src.mcp_server.tools.query_knowledge_hub import register_tool as register_query_tool
    register_query_tool(protocol_handler)
    
    # Import and register list_collections tool 导入并注册 list_collections 工具
    from src.mcp_server.tools.list_collections import register_tool as register_list_tool
    register_list_tool(protocol_handler)
    
    # Import and register get_document_summary tool 导入并注册 get_document_summary 工具
    from src.mcp_server.tools.get_document_summary import register_tool as register_summary_tool
    register_summary_tool(protocol_handler)

# 创建 MCP 服务器 工厂函数创建一个低级 MCP 服务器实例并为工具/列表和工具/调用注册必要的处理程序
def create_mcp_server(
    server_name: str,
    server_version: str,
    protocol_handler: Optional[ProtocolHandler] = None,
    register_tools: bool = True,
) -> Server:
    """
    流程:
    create_mcp_server()

            |
            |
    创建ProtocolHandler

            |
            |
    注册所有Tools

            |
            |
    创建mcp.server.lowlevel.Server

            |
            |
    绑定tools/list

            |
            |
    绑定tools/call

            |
            |
    返回Server
    Create and configure an MCP server with the protocol handler.

    This factory function creates a low-level MCP Server instance and
    registers the necessary handlers for tools/list and tools/call.

    Args:
        server_name: Name of the server.
        server_version: Version string.
        protocol_handler: Optional pre-configured protocol handler.
            If None, a new one will be created.
        register_tools: Whether to register default tools (default: True).

    Returns:
        Configured Server instance ready to run.
    """
    if protocol_handler is None:
        protocol_handler = ProtocolHandler(
            server_name=server_name,
            server_version=server_version,
        )

    # Register default tools if requested
    if register_tools:
        _register_default_tools(protocol_handler)

    # Create low-level server
    server = Server(server_name) # MCP官方 SDK 提供的服务器
    # 采用low-level Server, 因为要自己定义工具列表

    # Register tools/list handler
    @server.list_tools()
    async def handle_list_tools() -> List[types.Tool]:
        """Handle tools/list request."""
        return protocol_handler.get_tool_schemas()

    # Register tools/call handler
    @server.call_tool() # 装饰器作用: 把下面这个函数注册成为 MCP Server 处理 tools/call 请求的回调函数。
    # 如果不用装饰器就要写: 
    # server.register_call_handler(handle_call_tool)
    # 用装饰器更方便, 让 SDK 收到调用请求时自动转发到该函数
    async def handle_call_tool(
        name: str, arguments: Dict[str, Any]
    ) -> types.CallToolResult:
        """Handle tools/call request."""
        return await protocol_handler.execute_tool(name, arguments)

    # Store protocol handler on server for access
    server._protocol_handler = protocol_handler  # type: ignore[attr-defined]

    return server


# 获取 protocol_handler 从 server 实例
def get_protocol_handler(server: Server) -> ProtocolHandler:
    """Get the protocol handler from a server instance.

    Args:
        server: Server instance created by create_mcp_server.

    Returns:
        The ProtocolHandler associated with the server.

    Raises:
        AttributeError: If server was not created with create_mcp_server.
    """
    return server._protocol_handler  # type: ignore[attr-defined]

"""
MCP 的 stdio 模式本质是：Client 把 Server 当子进程拉起，用操作系统管道当“网线”，在上面跑 JSON-RPC。
Client（Cursor / 测试脚本）不是连端口，而是执行类似：
python -m src.mcp_server.server
并把子进程的 stdin / stdout / stderr 接上。


一句话
stdio MCP = 本机父子进程 + stdin/stdout 上的换行分隔 JSON-RPC；本项目用官方 mcp.server.stdio 接流，protocol_handler 负责把 tools/list、tools/call 转到具体工具。
没有 TCP 端口，所以天然是本地通信。
"""
