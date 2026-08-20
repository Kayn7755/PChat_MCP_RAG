"""
一次完整的 Agent 运行,包含“思考-执行”循环。
核心逻辑：
- 每次 step() 都先 THINKING,若有 tool_calls 则进入 EXECUTING 并执行工具
- 无工具调用时直接 FINISHED,不会进入 EXECUTING
- 每次 step() 结束后都更新状态机,通过 SSE 通知前端
- 支持最大步数限制,避免无限循环
- 出错时进入 ERROR 状态,通过 SSE 通知前端
"""

from __future__ import annotations # 启用“延迟解析类型注解”,让类型提示更灵活（避免前向引用问题,也有助于性能/循环引用处理）。

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from jchatmind_agent.chat_registry import ModelEndpoint
from jchatmind_agent.enums import AgentState
from jchatmind_agent.llm_client import chat_completion, normalize_tool_calls, parse_tool_arguments
from jchatmind_agent.schemas import SseMessage, SseMessageType, SseMetadata, SsePayload
from jchatmind_agent.tools import ToolSpec, openai_function_name_to_spec

logger = logging.getLogger(__name__)

MAX_STEPS = 20 # 最大步数,超过则认为任务结束。
DEFAULT_MAX_MESSAGES = 20 # 默认最大消息数,超过则进行消息裁剪。


def _format_agent_error(exc: BaseException) -> str:
    """把后台异常转成可展示给用户的短文案。"""
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return (
                "模型调用失败：请求过于频繁（429 限流）。"
                "请稍等 1～2 分钟后再试，或到智谱开放平台检查额度/频率限制。"
            )
        if code == 402:
            return "模型调用失败：账户余额不足或未开通付费（402）。请充值或更换可用的 API Key。"
        if code in (401, 403):
            return f"模型调用失败：API Key 无效或无权限（{code}）。请检查启动脚本中的密钥配置。"
        return f"模型调用失败：HTTP {code}。请查看后端日志了解详情。"
    return f"模型调用失败：{exc}"

# @dataclass 是 Python 标准库 dataclasses 里的装饰器，用来给类自动生成样板代码。
# 加上之后，一般会自动生成：
# __init__（按字段初始化）
# __repr__（方便打印）
# __eq__（按字段比较）
@dataclass
class KnowledgeBaseInfo: # 知识库信息类,包含 id、name、description。
    id: str # 知识库 id。
    name: str = "" # 知识库名称。
    description: str = "" # 知识库描述。

# Callable 是 类型注解, 相当于别名typedef
# Callable[[参数类型列表], 返回值类型]
# def save_msg(session_id: str, role: str, content: str, metadata: dict[str, Any] | None) -> str:
SaveMessageFn = Callable[[str, str, str, dict[str, Any] | None], str] # 保存消息函数类型,包含 session_id、role、content、metadata。
SseSendFn = Callable[[str, dict[str, Any]], None] # SSE 发送函数类型,包含 session_id、message。


@dataclass
class JChatMind: # JChatMind 类,包含 agent_id、name、description、system_prompt、chat_session_id、endpoint、tool_specs、knowledge_bases、temperature、top_p、max_messages、messages、save_message、sse_send、to_sse_message_vo。
    """
    Think-Execute 循环：
    - 关闭「自动串联工具执行」,由本类手动执行 tool_calls。
    - terminate 工具调用后进入 FINISHED。
    """
    agent_id: str
    name: str
    description: str
    system_prompt: str # Agent 的系统提示词
    chat_session_id: str # 聊天会话 id
    endpoint: ModelEndpoint # 模型端点
    tool_specs: list[ToolSpec] # 工具规范列表
    knowledge_bases: list[KnowledgeBaseInfo] = field(default_factory=list) # 知识库列表
    temperature: float = 0.7  # 用于缩放模型输出层（Logits）的概率分布： 低温（接近 0）：概率分布变得极其尖锐，模型几乎每次都会选择概率最高的下一个 Token，输出高度确定、严谨。 高温（接近 1 或更高）：概率分布变得平缓，低概率的 Token 被选中的几率增大，输出充满随机性和多样性。
    top_p: float = 1.0 # 核采样 按概率从高到低累加候选词，直到累计概率达到 p，再只在这些词里抽样。top_p = 1.0（项目默认）：几乎不截断，候选范围最大 top_p 越小（如 0.3）：只在高概率词里选，输出更稳、更保守。 top_p 越大（接近 1）：候选更广，输出更发散
    max_messages: int = DEFAULT_MAX_MESSAGES # 最大消息数
    messages: list[dict[str, Any]] = field(default_factory=list) # 消息列表, 当前这次 Agent 运行时的内存对话上下文
    save_message: SaveMessageFn | None = None # 该变量是 SaveMessageFn 类型或None,默认是None。
    sse_send: SseSendFn | None = None # 发送 SSE 消息函数，包含消息内容、角色、时间等。
    to_sse_message_vo: Callable[[dict[str, Any]], dict[str, Any]] | None = None # 转换消息为 SSE 消息格式函数，包含消息内容、角色、时间等。

    agent_state: AgentState = field(init=False) #Agent 运行时状态字段，并且不通过构造函数传入
    # agent_state 不是「配置」，而是 运行时内部状态，创建时不该由外部决定。

    # 生命周期由类自己管
    # 合法流转是 IDLE → PLANNING → THINKING → EXECUTING → FINISHED/ERROR。若构造时能传入任意状态，容易一上来就变成 FINISHED 或 ERROR，状态机就乱了。

    # 创建时语义固定
    # 工厂每次 create() 都是新建一个空闲 Agent，初始一定是 IDLE，没有「带状态创建」的需求。

    # 和配置字段职责分离
    # model、temperature、messages 等是输入配置；agent_state 是执行过程中的进度标记，应由 _set_state() / run() 更新。

    # 所以用 field(init=False) + __post_init__ 设为 IDLE，相当于强制「只能从空闲开始跑」。

    def __post_init__(self) -> None: # 只有该函数会初始化时自动执行(相当于构造函数)
        self.agent_state = AgentState.IDLE
        self._trim_messages() # 控制对话上下文长度,避免消息无限增长

    # 向前端发送 Agent 的“阶段状态事件”(通过 SSE)。
    def _emit_status(self, msg_type: SseMessageType, status_text: str, done: bool | None = None) -> None:
        if not self.sse_send: # sse_send是一个需要外界注入的回调函数, 用于正在实现想前端发送
            return
        msg = SseMessage(
            type=msg_type,
            payload=SsePayload(status_text=status_text, done=done),
            metadata=SseMetadata(),
        ) # 拼一条状态类 SSE 消息
        self.sse_send(self.chat_session_id, msg.to_json_dict()) # 调用 sse_send 函数推送消息

    # 改内部状态，并决定推什么状态文案
    def _set_state(self, state: AgentState) -> None: 
        self.agent_state = state
        if state == AgentState.PLANNING:
            self._emit_status(SseMessageType.AI_PLANNING, "规划中")
        elif state == AgentState.THINKING:
            self._emit_status(SseMessageType.AI_THINKING, "思考中")
        elif state == AgentState.EXECUTING:
            self._emit_status(SseMessageType.AI_EXECUTING, "执行中")
        elif state == AgentState.FINISHED:
            self._emit_status(SseMessageType.AI_DONE, "任务完成", done=True)
        elif state == AgentState.ERROR:
            self._emit_status(SseMessageType.AI_DONE, "执行失败", done=True)

    def _trim_messages(self) -> None: # 控制对话上下文长度,避免消息无限增长
        if self.max_messages <= 0: # 如果最大消息数小于等于0,则不进行裁剪
            return
        # 保留首条 system(若有),再截断尾部
        if not self.messages: # 如果消息列表为空,则不进行裁剪
            return
        sys_idx = None # 系统消息索引
        for i, m in enumerate(self.messages): # 遍历消息列表,找到第一条系统消息的位置。
            if m.get("role") == "system": # 系统提示词(system: 你是客服助手 ) 不裁剪
                sys_idx = i # 记录系统提示词的id, 后续跳过该id的消息
                break
        if sys_idx is not None: # 如果找到了系统消息,则保留系统消息,再截断尾部
            head = [self.messages[sys_idx]] # 保留系统消息
            tail = [m for j, m in enumerate(self.messages) if j != sys_idx][-self.max_messages + 1 :] # 截断尾部
            self.messages = head + tail
        else: # 如果没找到系统消息,则截断尾部
            self.messages = self.messages[-self.max_messages :] # 截断尾部
        # 裁剪前: system, A, B, C, D, E, F   （system + 6 条对话）
        # 裁剪后: system, D, E, F

    # 用来生成每轮思考时让模型调用知识库的系统提示。
    def _think_prompt(self) -> str: # 默认在每轮 _think() 时拼进去给大模型 API 的系统提示
        kb_text = ", ".join(
            f"{kb.id}({kb.name}): {kb.description}" for kb in self.knowledge_bases
        ) or "（无）"
        return f"""你是智能助手的「决策与回答」模块。根据对话上下文决定下一步。

【必须遵守】
1. 能直接回答时：用 assistant 文本直接回复用户，不要调用任何工具（包括 terminate）。
2. 需要知识库时：先调用 KnowledgeTool，拿到结果后再用文本回答用户。
3. terminate 仅在你已写好最终回答时使用，且必须把最终回答放进 message；禁止空调用 terminate。
4. 禁止在尚未回答用户问题时调用 terminate。

【额外信息】
- 可用知识库：{kb_text}
- 缺少上下文时优先用 KnowledgeTool 检索
"""

    def _openai_tools(self) -> list[dict[str, Any]]: # 把工具列表转换为 OpenAI 兼容的格式
        return [s.openai_schema for s in self.tool_specs]
        # 从 self.tool_specs 提取每个工具的 openai_schema
        # 返回给模型 API 的 tools 参数
        # 作用：告诉模型“你现在可调用哪些工具、参数怎么传”

    def _spec_by_fn_name(self) -> dict[str, ToolSpec]: # 把工具名映射到 ToolSpec 对象
        return openai_function_name_to_spec(self.tool_specs)
        # 把工具列表转换为 OpenAI 兼容的格式
        # 返回给模型 API 的 tools 参数
        # 作用：告诉模型“你现在可调用哪些工具、参数怎么传”

    def _log_tool_calls(self, calls: list[dict[str, Any]]) -> None: # 记录工具调用日志
        if not calls:
            logger.info("[ToolCalling] 无工具调用")
            return
        parts = []
        for i, c in enumerate(calls, 1):
            parts.append(
                f"[ToolCalling #{i}]\n- name      : {c.get('name')}\n- arguments : {c.get('arguments')}"
            )
        logger.info("========== Tool Calling ==========\n%s\n=================================", "\n\n".join(parts))
        # 没有工具调用就打印“无工具调用”
        # 有的话按序号格式化输出每个调用的 name 和 arguments
        # 作用：调试/排障时快速看模型到底想调用什么工具、传了什么参数

    def _persist_and_sse( # 把一条 Agent 产出的消息“落库并推送前端”
        self,
        *,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        mid = ""
        if self.save_message: # 如果 save_message 函数存在,则调用它保存消息s
            mid = self.save_message(self.chat_session_id, role, content, metadata) # self.save_message是外界输入的保存进数据库的函数
        if self.sse_send and self.to_sse_message_vo: # 如果 sse_send 函数存在,并且 to_sse_message_vo 函数存在,则调用它们保存消息
            vo = self.to_sse_message_vo( # 把消息转换为前端可用的格式
                {
                    "id": mid,
                    "sessionId": self.chat_session_id,
                    "role": role,
                    "content": content,
                    "metadata": metadata or {},
                }
            )
            msg = SseMessage( # 创建 SSE 消息对象
                type=SseMessageType.AI_GENERATED_CONTENT,
                payload=SsePayload(message=vo),
                metadata=SseMetadata(chat_message_id=mid or None),
            )
            self.sse_send(self.chat_session_id, msg.to_json_dict()) # 调用 sse_send 函数推送消息

    def _think(self) -> bool: # 一次模型调用；若有 tool_calls 返回 True（进入 execute）。 思考阶段核心函数 调用大模型做一轮决策,并判断是否要进入工具执行阶段
        think = self._think_prompt() # 生成系统提示
        api_messages: list[dict[str, Any]] = [*self.messages, {"role": "system", "content": think}] # 组装本轮模型请求并发起调用
        # 把历史消息 self.messages 复制一份
        # 在末尾追加本轮“决策系统提示”（think）
        # 得到本次发给 LLM 的完整上下文

        assistant = chat_completion( # 发起一次 OpenAI 兼容的聊天补全请求,并返回模型消息结果。
            self.endpoint, # 用哪个模型端点（URL/key/model）
            api_messages, # 本轮输入上下文
            self._openai_tools(), # 当前可调用工具 schema（function calling）
            temperature=self.temperature, # temperature/top_p：采样参数
            top_p=self.top_p,
            parallel_tool_calls=False, # 禁并行工具调用,按串行流程执行
        )

        content = assistant.get("content") or "" # 取文本内容
        tool_calls = normalize_tool_calls(assistant) # 解析工具调用

        asst_msg: dict[str, Any] = {"role": "assistant", "content": content or None} # 构造 assistant 消息对象 asst_msg
        if tool_calls: # 如果有工具调用,补上标准 tool_calls 结构（id/name/arguments）
            asst_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in tool_calls
            ]

        self.messages.append(asst_msg) # 写入内存消息并裁剪窗口
        self._trim_messages()

        meta: dict[str, Any] | None = None
        if tool_calls:
            # 前端 ToolCallDisplay 需要扁平结构 {id,type,name,arguments}，
            # 不要直接塞 OpenAI 的 function 嵌套格式，否则 arguments 为 undefined 会崩 UI。
            meta = {
                "toolCalls": [
                    {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "name": tc.get("name", ""),
                        "arguments": str(tc.get("arguments") or "{}"),
                    }
                    for tc in tool_calls
                ]
            }
        self._persist_and_sse(role="assistant", content=content, metadata=meta) # 持久化并推送 SSE
        self._log_tool_calls(tool_calls)
        return bool(tool_calls)

    # 工具执行阶段：模型在 _think 里决定要调哪些工具后，这里真正跑工具，并把结果写回上下文、入库、推前端
    # 传入_think需要的工具列表
    def _execute(self, tool_calls: list[dict[str, Any]]) -> None:
        spec_map = self._spec_by_fn_name() # 用工具名快速找到对应 ToolSpec.handler
        tool_messages: list[dict[str, Any]] = []
        terminate_answer = ""

        for tc in tool_calls: # 遍历每个 tool_call 执行
            fn = tc.get("name", "")
            tid = tc.get("id", "")
            args = parse_tool_arguments(str(tc.get("arguments", "{}")))
            spec = spec_map.get(fn)
            if not spec:
                result = f"错误：未知工具 {fn}"
            else:
                try:
                    result = spec.handler(**args)
                except Exception as e:
                    logger.exception("工具执行失败: %s", fn)
                    result = f"错误：工具执行异常 - {e}"
            if fn == "terminate":
                # 只有带有效最终回答的 terminate 才结束；空调用忽略，避免无回复
                cand = str(args.get("message") or result or "").strip()
                if cand and not cand.startswith("错误："):
                    terminate_answer = cand
                else:
                    result = (
                        result
                        or "错误：terminate 未提供最终回答。请直接用文本回答用户，或带 message 再调用 terminate。"
                    )
                    logger.warning("忽略空的 terminate 调用")
            tool_messages.append(
                {"role": "tool", "tool_call_id": tid, "content": result or ""}
            )

        self.messages.extend(tool_messages)
        self._trim_messages()

        for tc, tm in zip(tool_calls, tool_messages): # 持久化消息
            self._persist_and_sse(
                role="tool",
                content=tm.get("content") or "",
                metadata={
                    "toolCallId": tm.get("tool_call_id"),
                    "toolResponse": {
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "responseData": tm.get("content") or "",
                    },
                },
            )

        joined = "\n".join(
            f"工具{tc.get('name')}的返回结果为：{tm.get('content')}"
            for tc, tm in zip(tool_calls, tool_messages)
        )
        if joined:
            logger.info("工具调用结果：%s", joined)

        if terminate_answer:
            # 把最终回答落库并推前端（模型可能只在 tool args 里写了答案）
            self.messages.append({"role": "assistant", "content": terminate_answer})
            self._trim_messages()
            self._persist_and_sse(role="assistant", content=terminate_answer, metadata=None)
            self._set_state(AgentState.FINISHED)
            logger.info("任务结束")
        elif any(tc.get("name") == "terminate" for tc in tool_calls):
            only_terminate = all(tc.get("name") == "terminate" for tc in tool_calls)
            if only_terminate:
                # 整轮只有空 terminate：禁用工具强制出文本，避免用户看到空白
                logger.warning("忽略空的 terminate，强制生成文本回答")
                self._force_text_answer()
            else:
                nudge = (
                    "系统提示：terminate 未带有效 message。"
                    "请根据已有工具结果用文本回答用户，不要再次空调用 terminate。"
                )
                self.messages.append({"role": "system", "content": nudge})
                self._trim_messages()
                logger.info("空 terminate 已忽略，继续下一轮思考")

    def _force_text_answer(self) -> None:
        """在模型误调空 terminate 后，禁用工具再补一轮，拿到可见回答。"""
        nudge = (
            "系统提示：你刚才空调用了 terminate，用户还没收到回答。"
            "请现在直接用中文文本完整回答用户的问题，不要调用任何工具。"
        )
        api_messages: list[dict[str, Any]] = [
            *self.messages,
            {"role": "system", "content": nudge},
        ]
        assistant = chat_completion(
            self.endpoint,
            api_messages,
            tools=None,
            temperature=self.temperature,
            top_p=self.top_p,
            parallel_tool_calls=False,
        )
        content = (assistant.get("content") or "").strip()
        if not content:
            content = "抱歉，我这次没能生成有效回答，请再试一次。"
        asst_msg: dict[str, Any] = {"role": "assistant", "content": content}
        self.messages.append(asst_msg)
        self._trim_messages()
        self._persist_and_sse(role="assistant", content=content, metadata=None)
        self._set_state(AgentState.FINISHED)
        logger.info("已强制生成文本回答并结束任务")

    # 一轮对话结束标志: 模型不需要调用工具
    def step(self) -> None: # 一次 Agent 单步循环,是 “Think -> (可选) Execute” 的最小执行单元。
        self._set_state(AgentState.THINKING) # step时已经开始运行了
        had_tools = self._think()
        if not had_tools: # 不用工具,llm回答完就可以返回
            self._set_state(AgentState.FINISHED)
            return
            # 模型要调工具 → 说明还没做完，进入 _execute()，跑完后再进入下一轮 step()
            # 模型不调工具，只返回文本 → 说明已经能直接回答用户，任务结束 → FINISHED
        self._set_state(AgentState.EXECUTING) # 调用工具执行
        last = self.messages[-1]
        calls = normalize_tool_calls(last)
        self._execute(calls)

    # 把一次用户消息触发的任务，从启动跑到结束。
    def run(self) -> None: # Agent 总控函数,负责把一次任务完整跑完
        if self.agent_state != AgentState.IDLE: # 先做状态校验 只有 IDLE 才能启动,否则抛错（防止重复运行）
            raise RuntimeError("Agent is not idle")
        try:
            self._set_state(AgentState.PLANNING)
            for i in range(MAX_STEPS): # 循环执行 step()（最多 MAX_STEPS 次）
                if self.agent_state == AgentState.FINISHED:
                    break
                self.step()
                if i + 1 >= MAX_STEPS:
                    self._set_state(AgentState.FINISHED)
                    logger.warning("Max steps reached, stopping agent")
            if self.agent_state != AgentState.FINISHED:
                self._set_state(AgentState.FINISHED)
        except Exception as e:
            self._set_state(AgentState.ERROR)
            err_text = _format_agent_error(e)
            try:
                self._persist_and_sse(role="assistant", content=err_text, metadata=None)
            except Exception:
                logger.exception("写入失败提示消息时出错")
            logger.exception("Error running agent")
            raise RuntimeError("Error running agent") from e

    def __str__(self) -> str:
        return (
            f"JChatMind {{ name = {self.name}, description = {self.description}, "
            f"agentId = {self.agent_id}, systemPrompt = {self.system_prompt} }}"
        )


''' 
这个有THINKING ->EXECUTING循环吗

有,但是条件循环,不是每轮都必然执行 EXECUTING。

当前逻辑是：

每一轮 step() 先进入 THINKING
如果模型返回了 tool_calls,就切到 EXECUTING 并执行工具
如果没有工具调用,就直接 FINISHED,不会进入 EXECUTING
所以循环形态是：

有工具时：THINKING -> EXECUTING -> (下一轮) THINKING -> ...
无工具时：THINKING -> FINISHED
你这次日志里出现了 THINKING -> EXECUTING,说明该轮确实走到了工具执行分支。 '''


''' 系统消息（system message）就是给模型的最高优先级行为指令。

你可以把它理解成“AI 的岗位说明书/规则约束”,比如：

你是谁（角色）
你要遵守什么规则
回答风格、边界、禁止事项
工具使用策略（何时调用工具）
在消息结构里通常是：

{"role": "system", "content": "...规则..."}
和普通用户消息区别：

system：定义行为框架（通常应长期保留）
user：当前问题
assistant：模型回复 '''


''' 一般什么时候会有系统消息

一般在这几种场景会有系统消息：
会话初始化时
给模型设定默认角色和规则（最常见）。

Agent/助手配置里有 system_prompt 时
像你这个项目里,创建 JChatMind 前会把 Agent 的系统提示放进消息上下文。

需要强约束输出行为时
例如要求“必须简洁”“必须先检索再回答”“禁止编造”等。

切换任务/模式时
可能插入新的 system 消息覆盖或增强之前策略（有些框架会这么做）。

在你这个项目里,系统消息主要来源就是 Agent 配置里的 system_prompt,并在消息裁剪时被优先保留。 '''


''' SSE 是 Server-Sent Events,中文常叫“服务器推送事件”。

可以理解成：浏览器发起一次长连接,服务器持续往这个连接里推文本事件（单向：服务端 -> 客户端）。

特点：

基于 HTTP,前端用 EventSource 就能接
适合实时状态流：AI 思考中、执行中、消息增量等
单向推送（不像 WebSocket 是双向）
在你这个项目里,SSE 用来把 Agent 过程实时推给前端,比如：

AI_PLANNING
AI_THINKING
AI_EXECUTING
AI_GENERATED_CONTENT
AI_DONE
所以你终端看到的那些 SSE [sess-demo-1] {...},就是服务端在持续推送阶段和内容事件。 '''

''' 采样参数是什么

它们是控制模型“随机性/发散度”的两个参数。

temperature（温度）
越低：越稳定、保守、可复现（更像“选最可能答案”）
越高：越发散、创造性更强,但可能更不稳定
常见经验：0.2~0.8 偏稳,1.0+ 更放飞

top_p（核采样）
模型先按概率排序,只从“累计概率达到 p 的候选集合”里采样
越小：候选更少,更保守
越大：候选更多,更发散
top_p=1.0 基本不截断

简单记忆：
temperature 调“随机程度”
top_p 调“候选范围”
在工程里通常先固定一个再调另一个,避免两者同时大幅变化导致行为难以预测。 '''