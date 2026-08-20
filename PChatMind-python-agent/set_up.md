sk-7f016a1f118d44df821093cb53e651fb 
deepseek api


10a9a238f245406992b217b52d11d61f.IJQ8Z5gXMNjmtzRk
智谱 api

Remove-Item Env:JCHATMIND_DEEPSEEK_API_KEY
移除api

$env:JCHATMIND_ZHIPU_API_KEY="10a9a238f245406992b217b52d11d61f.IJQ8Z5gXMNjmtzRk"
设置api


python .\examples\in_memory_demo.py
启动后端demo

cd D:\rag_project\PChatMind-python-agent\ui
npm run dev
启动前端demo

---
# 后端demo启动完整流程:
```
cd D:\rag_project\PChatMind-python-agent
.\.venv\Scripts\Activate.ps1

$env:JCHATMIND_ZHIPU_API_KEY="10a9a238f245406992b217b52d11d61f.IJQ8Z5gXMNjmtzRk"
Remove-Item Env:JCHATMIND_DEEPSEEK_API_KEY -ErrorAction SilentlyContinue

python .\examples\in_memory_demo.py 
```
---
# 前端demo启动完整流程:
```
cd D:\rag_project\PChatMind-python-agent\ui
npm run dev
```
---
招聘要求与对应文件:
``` py
Prompt/Agent 配置：examples/in_memory_demo.py、jchatmind_agent/factory.py、jchatmind_agent/jchat_mind.py
RAG 能力：jchatmind_agent/rag_service.py
Tool Calling：jchatmind_agent/tools.py、jchatmind_agent/jchat_mind.py
OpenAPI/FastAPI 接口：jchatmind_app/main.py、jchatmind_app/api_schemas.py
工程化业务层：jchatmind_app/biz.py、jchatmind_app/repos.py、jchatmind_app/pool.py
模型接入（多模型）：jchatmind_agent/chat_registry.py、jchatmind_agent/llm_client.py
```

PostgreSQL : port 5432
密码: 123456