# JChatMind Agent 开发岗学习计划与八股文

> 目标：用 7 天把这个项目讲成一个完整的 Agent 工程案例，而不是只会说“我看过 Agent 代码”。
>
> 面试定位：这是一个基于 Python 的可配置 Agent + RAG + Tool Calling 聊天系统。`jchatmind_agent` 是 Agent 内核，`jchatmind_app` 是工程化接入层，`ui` 是前端演示层。

## 总体学习顺序

优先级从高到低：

1. `jchatmind_agent`：必须吃透，负责 Agent 主循环、工具调用、RAG、模型适配。
2. `jchatmind_app`：至少看懂调用链，负责 API、数据库、SSE、后台执行。
3. `examples/in_memory_demo.py`：用来跑最小闭环，方便面试时讲验证方式。
4. `ui`：不用深挖，只需知道前端如何发消息、如何接 SSE。

推荐每天固定输出三样东西：

- 一张调用链图，哪怕是手写。
- 一段 3 到 5 句话的口述总结。
- 3 个八股问答，第二天复述。

## Day 1：建立项目全局地图

### 要学的文件

- `jchatmind_agent/__init__.py`
- `examples/in_memory_demo.py`
- `jchatmind_agent/factory.py`
- `jchatmind_agent/jchat_mind.py`

### 核心知识点

- 项目分层：Agent 内核、FastAPI 应用层、React 前端层。
- 最小 Demo 怎么绕开数据库，只验证 Agent 主链路。
- `JChatMindFactory.create()` 如何把模型、工具、知识库、历史消息装配成一个可运行 Agent。
- `JChatMind.run()` 是 Agent 生命周期入口。

### 必会调用链

```text
examples/in_memory_demo.py
  -> default_registry_from_env()
  -> build_factory_with_defaults()
  -> factory.create(agent, session_id)
  -> JChatMind.run()
  -> step()
  -> _think()
  -> _execute()
  -> FINISHED
```

### 当天八股文

**Q1：这个项目是做什么的？**

A：这是一个 Python 版 Agent 聊天系统，支持多模型接入、系统提示词、历史消息窗口、工具调用、RAG 知识库检索和 SSE 实时状态推送。`jchatmind_agent` 负责 Agent 推理和工具执行，`jchatmind_app` 负责把它包装成 Web API 和持久化服务。

**Q2：为什么不能只看 `jchatmind_agent`？**

A：`jchatmind_agent` 能解释 Agent 内核，但不能解释用户消息如何触发 Agent、结果如何落库、状态如何回到前端。面试官常会追问完整工程链路，所以还要看 `jchatmind_app/biz.py`、`main.py`、`repos.py` 和 `sse_bus.py`。

**Q3：最小 Demo 的价值是什么？**

A：`examples/in_memory_demo.py` 不依赖数据库，能快速验证模型调用、Agent 主循环、工具调用和状态结束逻辑。它适合排查“Agent 内核是否能跑通”，但不能代表完整 Web 应用。

### 当天产出

- 画出项目三层架构图。
- 能用 1 分钟说明 `examples/in_memory_demo.py` 如何跑通一次 Agent。

## Day 2：吃透 Agent 主循环

### 要学的文件

- `jchatmind_agent/jchat_mind.py`
- `jchatmind_agent/enums.py`
- `jchatmind_agent/schemas.py`

### 核心知识点

- `AgentState` 状态机：`IDLE -> PLANNING -> THINKING -> EXECUTING -> FINISHED/ERROR`。
- `run()` 控制最大循环步数，避免 Agent 无限执行。
- `step()` 是单轮 Think -> optional Execute。
- `_think()` 调模型，判断是否有 `tool_calls`。
- `_execute()` 执行工具，把工具结果追加回消息上下文。
- `_persist_and_sse()` 同时负责消息持久化和事件推送。

### 重点函数

- `JChatMind.__post_init__`
- `JChatMind._trim_messages`
- `JChatMind._think_prompt`
- `JChatMind._think`
- `JChatMind._execute`
- `JChatMind.step`
- `JChatMind.run`
- `SseMessage.to_json_dict`

### 当天八股文

**Q1：Agent 主循环是怎么设计的？**

A：这个项目采用 Think -> Execute 循环。每轮先进入 `THINKING`，调用大模型生成回答或工具调用；如果没有工具调用，就直接结束；如果有工具调用，就进入 `EXECUTING` 执行本地工具，把结果作为 tool message 加回上下文，再进入下一轮思考，直到完成或达到最大步数。

**Q2：为什么要有 `MAX_STEPS`？**

A：Agent 调工具后可能继续让模型思考，如果模型一直调用工具，就会陷入死循环。`MAX_STEPS` 是保护机制，保证一次任务最多执行固定轮数，避免资源失控。

**Q3：消息裁剪为什么要保留 system message？**

A：system message 是 Agent 的行为约束，比如角色、边界、工具策略。历史消息过长需要裁剪，但 system prompt 应优先保留，否则 Agent 可能丢失角色设定和安全约束。

### 当天产出

- 用自己的话解释 `run -> step -> _think -> _execute`。
- 记录 assistant message 和 tool message 的结构差异。

## Day 3：模型调用与多模型接入

### 要学的文件

- `jchatmind_agent/llm_client.py`
- `jchatmind_agent/chat_registry.py`
- `jchatmind_app/config.py`

### 核心知识点

- OpenAI-compatible `/chat/completions` 请求结构。
- `ModelEndpoint` 抽象：`base_url`、`api_key`、`model`。
- `ChatClientRegistry` 根据模型名选择 DeepSeek 或 GLM。
- `normalize_tool_calls()` 把模型返回的工具调用统一成内部格式。
- `parse_tool_arguments()` 容错解析工具参数 JSON。
- 配置来自环境变量，前缀是 `JCHATMIND_`。

### 重点函数

- `chat_completion`
- `normalize_tool_calls`
- `parse_tool_arguments`
- `ChatClientRegistry.get`
- `default_registry_from_env`
- `get_settings`

### 当天八股文

**Q1：这个项目如何支持多模型？**

A：项目把模型连接信息封装成 `ModelEndpoint`，再用 `ChatClientRegistry` 维护模型名到 endpoint 的映射。Agent 配置里只保存模型 key，例如 `deepseek-chat` 或 `glm-4.6`，运行时通过 registry 找到对应 base_url、api_key 和真实模型名。

**Q2：为什么说它是 OpenAI 兼容调用？**

A：`llm_client.py` 请求的是 `{base_url}/chat/completions`，请求体包含 `model`、`messages`、`tools`、`tool_choice`、`temperature`、`top_p`，这和 OpenAI Chat Completions 的通用格式一致，所以可以接 DeepSeek、GLM 这类兼容接口。

**Q3：工具参数为什么要做 JSON 容错？**

A：模型返回的 function arguments 通常是 JSON 字符串，但实际可能格式错误。`parse_tool_arguments()` 解析失败时返回空字典，避免整个 Agent 崩溃，同时保留日志方便定位。

### 当天产出

- 能画出 `model name -> registry -> endpoint -> /chat/completions`。
- 准备一段“如何新增一个模型供应商”的口述。

## Day 4：Tool Calling 机制

### 要学的文件

- `jchatmind_agent/tools.py`
- `jchatmind_agent/jchat_mind.py`

### 核心知识点

- `ToolSpec` 是工具元数据，包含注册名、描述、类型、OpenAI schema、handler。
- 工具分为固定工具和可选工具。
- 固定工具：`KnowledgeTool`、`terminate`。
- 可选工具：`dataBaseTool`、`emailTool`、`echoTool`。
- schema 给模型看，handler 在本地真正执行。
- `resolve_runtime_tools()` 根据 Agent 配置裁剪可用工具。
- `_execute()` 根据模型返回的 function name 找到本地 handler 并执行。

### 重点函数

- `ToolSpec`
- `_knowledge_tool_schema`
- `_terminate_schema`
- `_database_schema`
- `_email_schema`
- `DatabaseToolBackend.query`
- `EmailToolBackend.send`
- `build_default_tool_specs`
- `resolve_runtime_tools`
- `openai_function_name_to_spec`
- `JChatMind._execute`

### 当天八股文

**Q1：Tool Calling 的完整链路是什么？**

A：后端先把工具 schema 传给大模型，模型决定是否返回 `tool_calls`。Agent 收到后解析 function name 和 arguments，用 function name 找到本地 `ToolSpec.handler` 执行，再把执行结果作为 tool message 放回上下文，最后继续调用模型生成最终回答或下一步动作。

**Q2：schema 和 handler 的区别是什么？**

A：schema 是给模型看的接口说明，告诉模型工具叫什么、能做什么、参数是什么；handler 是后端真实执行逻辑，比如查数据库、发邮件、查知识库。模型只决定“调用哪个工具和传什么参数”，真正执行必须由后端完成。

**Q3：为什么要区分固定工具和可选工具？**

A：固定工具是 Agent 基础能力，比如知识库检索和结束循环；可选工具涉及权限或风险，比如数据库查询、发邮件，需要按 Agent 配置开启。这样可以控制不同 Agent 的能力边界。

**Q4：数据库工具安全吗？**

A：当前做了基础限制，只允许 SQL 以 `SELECT` 开头，避免写操作。但这只是最小防护，生产环境还应增加 SQL AST 校验、超时、行数限制、字段脱敏和权限隔离。

### 当天产出

- 能讲清楚 `ToolSpec` 五个字段各自作用。
- 尝试解释如果新增 `getCurrentTime` 工具，需要改哪些位置。

## Day 5：RAG 知识库与向量检索

### 要学的文件

- `jchatmind_agent/rag_service.py`
- `jchatmind_agent/tools.py`
- `jchatmind_app/biz.py`
- `jchatmind_app/markdown_sections.py`
- `jchatmind_app/document_storage.py`
- `jchatmind_app/repos.py`

### 核心知识点

- `RagService` 抽象了两个能力：`embed()` 和 `similarity_search()`。
- 默认 embedding 通过 Ollama / LangChain 调用 `bge-m3`。
- 检索存储依赖 PostgreSQL + pgvector。
- 主要向量表是 `chunk_bge_m3`。
- Markdown 上传后按标题切分章节，生成 embedding，写入 chunk 表。
- Agent 通过 `KnowledgeTool` 调用 `rag.similarity_search()`。

### RAG 链路

```text
上传 Markdown
  -> 保存文件
  -> parse_markdown_sections()
  -> 每个 section 生成 embedding
  -> 写入 chunk_bge_m3

用户提问
  -> Agent 判断需要查知识库
  -> KnowledgeTool(kbsId, query)
  -> query 生成 embedding
  -> pgvector 相似度检索
  -> chunk 文本返回给模型
```

### 当天八股文

**Q1：RAG 在这个项目里解决什么问题？**

A：RAG 用来让模型回答私有知识库内容。模型本身不知道项目上传的 Markdown 文档，所以需要先把文档切分、向量化、入库；用户提问时再做相似度检索，把命中的文本片段交给模型作为外部上下文。

**Q2：这个项目的 RAG 流程是什么？**

A：文档上传后保存到本地文件系统，Markdown 按标题切分为章节，每个章节通过 Ollama 或 LangChain 生成 embedding，再写入 PostgreSQL 的 pgvector 表。查询时把 query 也转成向量，通过 pgvector 的距离排序找出 top-k chunk，返回给 Agent 的知识库工具。

**Q3：为什么用 pgvector？**

A：pgvector 可以在 PostgreSQL 内直接存储和检索向量，便于和业务数据放在同一个数据库里管理。对中小规模知识库来说，它比单独引入向量数据库更简单，部署成本更低。

**Q4：RAG 可能失败在哪里？**

A：常见问题包括切分粒度不合理、embedding 模型效果差、top-k 太小或太大、知识库没有命中文档、检索结果污染上下文，以及模型没有正确使用检索结果。

### 当天产出

- 能讲清楚 `embed -> chunk_bge_m3 -> similarity_search -> KnowledgeTool`。
- 总结 3 个 RAG 优化点：更好的切分、重排序、引用来源返回。

## Day 6：业务层工程化接入

### 要学的文件

- `jchatmind_app/main.py`
- `jchatmind_app/biz.py`
- `jchatmind_app/repos.py`
- `jchatmind_app/pool.py`
- `jchatmind_agent/event_bridge.py`
- `jchatmind_app/sse_bus.py`

### 核心知识点

- FastAPI 提供 REST 接口和 SSE 接口。
- `create_chat_message()` 保存用户消息后触发后台 Agent。
- `run_agent_in_background()` 使用线程池异步执行 Agent。
- `repos.py` 负责数据库 CRUD。
- `pool.py` 维护 psycopg2 连接池。
- `sse_bus.py` 维护 session_id 到异步队列的映射。
- SSE 用于实时推送状态，不是双向通信。

### 完整请求链路

```text
前端 POST /api/chat-messages
  -> main.py api_create_message()
  -> biz.create_chat_message()
  -> repos.message_insert()
  -> run_agent_in_background()
  -> factory.create()
  -> JChatMind.run()
  -> assistant/tool message 落库
  -> sse_bus.send_message()
  -> 前端 EventSource 收到增量事件
```

### 当天八股文

**Q1：用户点发送后，后端发生了什么？**

A：前端调用 `/api/chat-messages`，后端先把用户消息写入 `chat_message`，然后根据 agent_id 加载 Agent 配置，在线程池里异步启动 Agent。Agent 运行过程中生成 assistant/tool 消息，继续写库，并通过 SSE 推给前端。

**Q2：为什么 Agent 要后台异步执行？**

A：模型调用和工具执行可能耗时较长，如果同步阻塞 HTTP 请求，前端体验会很差，也容易超时。后台线程可以让接口快速返回，同时用 SSE 持续推送执行进度和生成结果。

**Q3：为什么使用 SSE 而不是 WebSocket？**

A：这个项目主要是服务端向前端单向推送状态和消息增量，SSE 基于 HTTP，前端用 EventSource 就能接入，实现简单。WebSocket 更适合双向实时通信，这里暂时不是必须。

**Q4：HTTP 200 但业务 code=500 怎么理解？**

A：这个项目的异常处理会返回 HTTP 200，同时在 JSON 里用 `code=500` 表示业务失败。排查时不能只看 HTTP 状态码，还要看响应体里的 `code` 和 `message`。

### 当天产出

- 能完整讲一遍“前端发消息到 Agent 结果回前端”的链路。
- 准备一个排障案例：DB 不可用、模型 Key 错误、SSE 断开。

## Day 7：前端联调、演示与面试表达

### 要学的文件

- `ui/src/api/http.ts`
- `ui/src/api/api.ts`
- `ui/src/components/views/AgentChatView.tsx`
- `ui/src/components/SideMenu.tsx`
- `ui/vite.config.ts`
- `requirements.txt`
- `set_up.md`

### 核心知识点

- 前端通过 `/api` 调 FastAPI，开发时 Vite proxy 转发到 `127.0.0.1:8080`。
- 聊天页通过 `EventSource` 连接 `/sse/connect/{session_id}`。
- `AgentChatView` 收到 `AI_GENERATED_CONTENT` 后追加消息，收到状态事件后更新状态展示。
- PowerShell 下 `npm run build` 可能被 `npm.ps1` 执行策略拦截，可以用 `npm.cmd run build`。
- `requirements.txt` 当前混入了非依赖内容和疑似密钥，投递前必须清理并轮换密钥。

### 当天八股文

**Q1：前端怎么实时显示 Agent 状态？**

A：聊天页创建 `EventSource` 连接后端 SSE 接口。后端在 Agent 状态变化或生成消息时推送事件，前端根据事件类型更新 UI，例如 `AI_THINKING` 显示思考中，`AI_EXECUTING` 显示执行中，`AI_GENERATED_CONTENT` 追加新消息。

**Q2：开发环境前后端如何联调？**

A：前端 Vite 默认跑在 5173，后端 FastAPI 默认跑在 8080。`vite.config.ts` 把 `/api` 和 `/sse` 代理到后端，所以前端代码可以统一请求相对路径，不需要直接写死后端地址。

**Q3：投递前这个项目最需要补什么？**

A：第一是清理敏感信息，不要把 API Key 写进 `requirements.txt` 或文档；第二是补数据库初始化 SQL，因为代码依赖 `agent`、`chat_session`、`chat_message`、`knowledge_base`、`document`、`chunk_bge_m3` 等表；第三是补 README，让面试官能快速跑通。

### 当天产出

- 准备 30 秒、2 分钟、5 分钟三个版本的项目介绍。
- 列一页“项目风险与优化点”，显示工程意识。

## 必背八股文总集

### 1. 项目介绍

**问：介绍一下你的 Agent 项目。**

答：这个项目是一个 Python 版 Agent + RAG 聊天系统。用户可以创建不同智能体，配置模型、系统提示词、可用工具和知识库。用户发消息后，后端会异步启动 Agent，Agent 通过 OpenAI 兼容接口调用大模型，根据模型返回决定是否调用工具，比如知识库检索、数据库查询、邮件发送或终止任务。执行过程和生成内容通过 SSE 实时推给前端，消息和知识库数据持久化在 PostgreSQL 中，向量检索使用 pgvector。

### 2. Agent 主循环

**问：Agent 是如何运行的？**

答：核心是 `JChatMind.run()`。它先进入规划状态，然后循环执行 `step()`。每个 step 先 `_think()` 调用大模型，如果模型没有返回工具调用，就完成任务；如果返回了 tool_calls，就 `_execute()` 执行工具，把工具结果作为 tool message 写回上下文，再进入下一轮思考。为了避免死循环，设置了最大步数。

### 3. Tool Calling

**问：你怎么实现工具调用？**

答：工具统一抽象成 `ToolSpec`，里面有工具注册名、描述、类型、OpenAI function schema 和本地 handler。调用模型时把 schema 传给模型，模型返回 tool_calls 后，后端根据 function name 找到对应 handler 执行，再把执行结果写成 tool message 回灌给模型。

### 4. RAG

**问：RAG 是怎么落地的？**

答：项目先把上传的 Markdown 文档保存到本地，然后按标题切分章节，用 Ollama 或 LangChain 生成 embedding，写入 PostgreSQL 的 pgvector 表 `chunk_bge_m3`。用户提问时，知识库工具把 query 向量化，在 pgvector 中做相似度检索，把命中的文本片段返回给模型。

### 5. 多模型接入

**问：怎么支持 DeepSeek 和 GLM？**

答：项目用 `ModelEndpoint` 抽象模型端点，用 `ChatClientRegistry` 维护模型名到 endpoint 的映射。Agent 配置只保存模型 key，运行时查 registry 得到 base_url、api_key 和 model，再用统一的 OpenAI 兼容请求发起调用。

### 6. 历史消息窗口

**问：上下文太长怎么办？**

答：项目用 `message_length` 控制历史消息窗口，`_trim_messages()` 会裁剪历史消息，同时优先保留 system message，避免 Agent 丢失角色设定和行为约束。

### 7. SSE

**问：为什么用 SSE？**

答：Agent 运行过程主要是服务端持续向前端推送状态和内容，属于单向实时通信，SSE 更轻量，浏览器原生 EventSource 就支持。它适合推送 `AI_THINKING`、`AI_EXECUTING`、`AI_GENERATED_CONTENT` 这类事件。

### 8. 后台异步执行

**问：为什么不在接口里同步跑 Agent？**

答：模型调用和工具执行耗时不稳定，同步执行容易导致请求阻塞或超时。项目用线程池后台运行 Agent，HTTP 请求只负责保存用户消息并触发任务，执行过程通过 SSE 返回给前端。

### 9. 数据库设计

**问：核心表有哪些？**

答：主要有 `agent` 存智能体配置，`chat_session` 存会话，`chat_message` 存用户、助手和工具消息，`knowledge_base` 存知识库，`document` 存上传文档元数据，`chunk_bge_m3` 存文档切片和 embedding。

### 10. 排障

**问：你怎么定位前后端联调问题？**

答：我会先看前端是否有 Vite proxy 错误，再直接请求后端 API 判断服务是否存活；如果 HTTP 通但业务失败，就看响应体里的 `code` 和 `message`；如果模型失败，区分是 key、额度、网络还是接口格式问题；如果 RAG 失败，再看 Ollama、PostgreSQL 和 pgvector 表是否正常。

### 11. 安全与工程风险

**问：这个项目目前有什么问题？**

答：第一，配置文件里不能出现明文 API Key，应该放到 `.env` 并加入 `.gitignore`；第二，需要补数据库初始化 SQL；第三，数据库查询工具只靠正则限制 SELECT 还不够安全；第四，RAG 目前只支持 Markdown，切分和检索策略比较简单；第五，缺少系统化测试和健康检查接口。

### 12. 如何新增一个工具

**问：如果要新增一个工具，你会怎么做？**

答：我会先在 `tools.py` 里定义 OpenAI function schema，再写本地 handler，然后在 `build_default_tool_specs()` 里注册成 `ToolSpec`。如果是高风险工具，就标记为 OPTIONAL，让 Agent 配置决定是否开启。最后通过 prompt 或测试用例验证模型是否能正确触发工具调用。

## 面试口述模板

### 30 秒版本

我做的是一个 Python Agent + RAG 聊天系统。核心模块 `jchatmind_agent` 实现了 Think -> Tool Execute 的 Agent 循环，支持 OpenAI 兼容模型、多模型切换、工具调用和知识库检索；`jchatmind_app` 用 FastAPI 把它工程化，负责消息持久化、后台异步执行和 SSE 实时推送；知识库部分用 Ollama embedding 加 PostgreSQL pgvector 做相似度检索。

### 2 分钟版本

这个项目可以分三层讲。第一层是 Agent 内核，`JChatMind.run()` 控制整体生命周期，每一轮先调用模型思考，如果模型返回工具调用，就执行本地工具并把结果写回上下文，否则结束任务。第二层是能力层，包括 `llm_client.py` 的 OpenAI 兼容模型调用、`tools.py` 的 ToolSpec 和工具分发、`rag_service.py` 的 embedding 与向量检索。第三层是工程接入层，FastAPI 接收用户消息并写入数据库，然后用线程池异步跑 Agent，运行过程通过 SSE 推给前端。这个项目体现了我对 Agent Loop、Tool Calling、RAG、异步任务和前后端实时联调的理解。

### 5 分钟版本提纲

1. 项目定位：可配置 Agent + RAG 聊天系统。
2. 架构分层：`jchatmind_agent`、`jchatmind_app`、`ui`。
3. 主链路：用户消息入库 -> 后台 Agent -> 模型调用 -> 工具执行 -> SSE 推送。
4. Agent 内核：`run/step/_think/_execute`。
5. Tool Calling：schema 给模型，handler 本地执行。
6. RAG：Markdown 切分 -> embedding -> pgvector -> KnowledgeTool。
7. 工程化：FastAPI、PostgreSQL、线程池、SSE。
8. 风险与优化：密钥管理、建表脚本、SQL 安全、RAG 质量、测试。

## 投递前检查清单

- [ ] 能不看代码讲清 `JChatMind.run()`。
- [ ] 能说出 `ToolSpec` 的五个字段。
- [ ] 能讲清 `KnowledgeTool` 如何触发 pgvector 检索。
- [ ] 能讲清用户发消息后完整后端链路。
- [ ] 能解释为什么使用后台线程和 SSE。
- [ ] 能说明项目目前的不足和优化方案。
- [ ] 清理 `requirements.txt` 里的非依赖内容和疑似密钥。
- [ ] 补充数据库初始化 SQL 或 README 说明。
- [ ] 准备一个可运行 Demo 截图或日志。

## 重点文件速查表

| 文件 | 面试价值 | 你要能讲什么 |
| --- | --- | --- |
| `jchatmind_agent/jchat_mind.py` | 最高 | Agent 主循环、状态机、工具执行 |
| `jchatmind_agent/tools.py` | 最高 | ToolSpec、function schema、handler、权限裁剪 |
| `jchatmind_agent/rag_service.py` | 最高 | RAG 抽象、embedding、pgvector 检索 |
| `jchatmind_agent/llm_client.py` | 高 | OpenAI 兼容调用、tool_calls 解析 |
| `jchatmind_agent/factory.py` | 高 | Agent 配置装配、历史消息转换 |
| `jchatmind_agent/chat_registry.py` | 中高 | 多模型注册与切换 |
| `jchatmind_app/biz.py` | 高 | 业务入口、消息触发 Agent、文档入库 |
| `jchatmind_app/main.py` | 高 | FastAPI 路由、SSE 接口 |
| `jchatmind_app/repos.py` | 中高 | 表结构感知、持久化操作 |
| `jchatmind_app/sse_bus.py` | 中 | session 队列、事件推送 |
| `examples/in_memory_demo.py` | 中高 | 最小可运行闭环 |
| `ui/src/components/views/AgentChatView.tsx` | 中 | 前端发消息与 EventSource |



# 项目s补充
合适，**但它更适合投“AI 应用开发 / Agent 开发 / 大模型应用工程”方向**，不是很强匹配“模型训练、算法研究、深度学习框架训练”方向。

我给你的判断是：**匹配度 75% 左右，能投，但简历表述要包装准。**

**匹配的地方**
这个项目能很好覆盖招聘要求里的这些点：

1. **大语言模型应用**
   - 项目接了 DeepSeek / 智谱 GLM。
   - 有 OpenAI-compatible `/chat/completions` 调用。
   - 有模型切换、temperature、top_p、历史消息窗口。

2. **Prompt / Agent 设计**
   - 有 `system_prompt`。
   - 有 Agent 的 `_think_prompt()`。
   - 有工具 schema，引导模型调用工具。
   - 可以说你做过 Prompt 约束、工具调用提示、Agent 行为控制。

3. **AI 应用开发经验**
   - FastAPI 后端。
   - React 前端。
   - PostgreSQL 持久化。
   - SSE 实时推送。
   - 这是一个完整 AI 应用，不是只写了一个脚本。

4. **LLM API 调用与调优**
   - `llm_client.py` 里有模型 API 调用。
   - `chat_registry.py` 支持多模型配置。
   - `factory.py` 支持 Agent 参数装配。
   - 这点和“理解大语言模型基本原理及 API 调用方法”很匹配。

5. **RAG / 知识库**
   - Markdown 文档上传。
   - Ollama / LangChain embedding。
   - PostgreSQL + pgvector 向量检索。
   - `KnowledgeTool` 给 Agent 调用知识库。

6. **业务转化**
   - 这个项目不是纯算法 demo，而是一个可用的聊天系统。
   - 能体现“把 AI 能力落到业务系统里”。

**不够匹配的地方**
招聘要求里也有几块，这个项目目前偏弱：

1. **数据清洗、特征工程**
   - 项目里没有明显的数据清洗流程。
   - 文档处理只有 Markdown 切分，算轻量文本处理，不算完整数据工程。

2. **模型训练 / 微调 / 评估**
   - 项目没有训练模型。
   - 没有 PyTorch / TensorFlow 训练代码。
   - 没有系统化评估，比如准确率、召回率、RAG 命中率、Prompt A/B 测试。

3. **算法与数学基础展示**
   - 项目用了 embedding 和向量检索，但没有手写算法或模型训练。
   - 如果面试官偏算法，会追问线性代数、概率统计、优化理论、Transformer、attention、反向传播等。

所以你投这个岗位可以，但简历里不要写成“模型训练项目”，应该写成：

> 基于大语言模型的 Agent + RAG 智能问答系统

或者：

> 企业知识库智能体系统：支持多模型接入、工具调用、RAG 检索与实时推送

**建议你简历这样写**
可以写 4 条：

- 设计并实现基于 Python 的 LLM Agent 执行框架，支持 `Think -> Tool Execute` 循环、历史消息裁剪、系统提示词注入和多轮工具调用。
- 接入 DeepSeek / GLM 等 OpenAI 兼容模型，封装统一模型调用层，支持 temperature、top_p、模型路由和 tool_calls 解析。
- 实现 RAG 知识库能力，支持 Markdown 文档切分、Ollama embedding、PostgreSQL + pgvector 相似度检索，并通过 `KnowledgeTool` 接入 Agent。
- 基于 FastAPI + SSE 实现异步 Agent 执行与实时状态推送，前端可展示 AI 规划、思考、执行和生成内容过程。

**为了更贴合这个岗位，建议你补 3 个小东西**
不一定要大改，补了之后就更像招聘要求里的项目：

1. **补一个 Prompt 优化文档**
   - 记录 3 版 prompt。
   - 对比回答质量。
   - 写清楚你怎么减少幻觉、怎么引导调用知识库、怎么控制回答格式。

2. **补一个 RAG 评估脚本或文档**
   - 准备 10 个问题。
   - 记录是否命中文档。
   - 记录回答是否正确。
   - 简单算一下命中率、准确率。

3. **补一个数据处理说明**
   - Markdown 如何切分。
   - 为什么按标题切。
   - chunk 太长/太短有什么影响。
   - 后续可以怎么优化，比如滑动窗口、重排序、引用来源。

**结论**
这个项目**可以用来投这个岗位**，尤其适合突出：

- Python 开发
- 大模型 API
- Prompt 工程
- Agent
- Tool Calling
- RAG
- AI 应用落地

但你要主动承认它不是模型训练项目。面试时可以说：

> 这个项目重点不是从零训练大模型，而是围绕大模型 API 做应用层 Agent 工程化，包括提示词设计、工具调用、知识库检索、异步执行和前后端联调。模型训练和评估方向我目前在补充 RAG 评估、Prompt 对比实验和深度学习基础。

还有一个很重要的小提醒：**投递前别直接把当前项目打包发出去**，因为 `requirements.txt` 和文档里疑似有 API Key 明文，必须先清理。
