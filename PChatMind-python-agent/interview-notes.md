# PChatMind Demo 面试速记
“外部知识库在哪”： 对模型来说是外部知识；对系统来说就在你自己的 PostgreSQL + 本地文件存储里。
## 1. 项目定位与核心能力

- 这是一个基于 `FastAPI + Agent + RAG` 的智能对话系统。
- 提供两种运行方式：
  - **最小 Demo**：`examples/in_memory_demo.py`，不依赖数据库，验证 Agent 主链路。
  - **完整应用**：`python -m jchatmind_app` + `ui` 前端，依赖 PostgreSQL。
- 支持多模型路由（如 DeepSeek、智谱），通过环境变量切换。

## 2. 架构拆分（高频面试题）

- `jchatmind_agent`：Agent 核心，包含推理循环、工具调用、模型请求、RAG 接口。
- `jchatmind_app`：Web API 层（FastAPI），负责会话、消息、知识库、文档等接口。
- `ui`：前端页面，开发模式由 Vite 代理 `/api`、`/sse` 到后端。
- 数据持久化：默认 PostgreSQL；向量检索依赖 `pgvector`（`vector` 类型）。

## 3. 一次完整请求的链路

1. 前端发起 `/api/chat-messages`。
2. 后端保存用户消息，触发 Agent 异步执行。
3. Agent 调模型接口（Chat Completions）。
4. 若模型返回工具调用（如 `terminate`），执行工具并写入工具消息。
5. SSE 通道 `/sse/connect/{session_id}` 推送消息增量给前端。
6. Agent 结束，状态进入 `FINISHED`。

## 4. 这次实操暴露的关键知识点

### 4.1 Python 虚拟环境与 Windows 启动器问题

- 报错现象：`Fatal error in launcher... pip.exe`
- 本质原因：`.venv` 被移动后，`pip.exe` 内部记录旧路径。
- 常见解法：
  - 临时：`python -m pip install -r requirements.txt`
  - 永久：删除并重建 `.venv`

### 4.2 HTTP 状态码定位能力

- `402 Payment Required`：代码通常没问题，代表模型平台账号额度/计费问题。
- `ECONNREFUSED 127.0.0.1:8080`：前端代理目标端口没有服务在监听。
- `HTTP 200 + 业务 code=500`：网关通，但业务逻辑失败（如数据库未连接）。

### 4.3 环境变量作用域（终端隔离）

- PowerShell 中 `$env:XXX` 只在当前终端会话生效。
- 前后端在不同终端启动时，要分别确认各自依赖是否配置完毕。

## 5. 为什么“无数据库模式”前端看起来没反应

- 允许 `JCHATMIND_ALLOW_START_WITHOUT_DB=1` 仅表示后端进程可启动。
- 但前端首页依赖的核心接口（`/api/agents`、`/api/chat-sessions`、`/api/knowledge-bases`）仍需数据库。
- 因此会出现：页面打开了，但关键交互返回 `code=500`。
- 结论：无库模式适合 API 联调/启动验证，不适合完整 UI 业务演示。

## 6. 常见追问与回答模板

### Q1：你是如何快速判断问题在前端还是后端？

- 我先看 Vite 日志是否出现 `proxy error`。
- 再用 `curl http://127.0.0.1:8080/api/tools` 验证后端存活。
- 如果网络通但业务失败，再看响应体的业务码与错误消息。

### Q2：你如何保证 Demo 可复现？

- 固化命令顺序：依赖安装 -> 环境变量 -> 启动后端 -> 启动前端 -> 接口自检。
- 给出最小成功判据（如 `AgentState.FINISHED`）。
- 将关键配置转成 `.env` 或脚本，减少人工操作差异。

### Q3：你如何处理第三方模型不稳定或额度问题？

- 做多供应商兜底（DeepSeek/智谱切换）。
- 对 `4xx/5xx` 做可观察性日志，区分配置错误与平台错误。
- 对核心演示准备备用 Key/备用模型，避免单点失败。

## 7. 可优化点（加分项）

- 增加“无数据库前端降级模式”：在 DB 不可用时返回空列表而非硬错误。
- 补充项目级 `README`：一键启动命令、依赖矩阵、常见错误。
- 增加健康检查接口：例如 `/health`（DB、LLM、SSE 状态）。
- 提供 `docker-compose`：一次拉起 Postgres + 后端 + 前端，降低上手成本。

## 8. 你这次已经跑通的内容（可在面试中强调）

- 成功运行内存版 Agent Demo，并完成模型调用与工具调用闭环。
- 能通过日志和状态码快速定位问题（额度、端口、数据库依赖）。
- 理解了前后端联调的依赖关系及运行边界。

## 9. 30 秒口述版（可直接背）

“我把这个项目按两条链路跑通了：一个是纯内存 Demo，用来验证 Agent 推理、工具调用和 SSE 事件闭环；另一个是完整前后端链路，确认了前端核心接口依赖 PostgreSQL。排障时我通过 HTTP 状态码和 Vite 代理日志快速分层定位：402 是模型平台额度问题，ECONNREFUSED 是后端没监听，200 但 code=500 是业务层数据库不可用。这套方法能让我在面试现场快速定位并恢复演示环境。”  

