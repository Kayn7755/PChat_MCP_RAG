"""
路由层
按模块划分

模块化路由: 把每个业务功能的接口拆分到独立文件中, 再统一挂载到主应用里
from fastapi import APIRouter 

# 创建API实例       前缀              分组(体现在交互式文档中)
router = APIRouter(prefix="/api/ai", tags=["AI问答"])

# 再写路由时就不用@app了, 而是@路由实例, 其余部分一样       
@router.post("/chat", summary="AI 智能问答")
async def ai_chat(request: ChatRequest)

# 核心区别：@app 挂在应用本体上，@router 挂在可拆分的路由模块上，最后再挂进 app。

app中通过app.include_router(news.router)挂载
news.router: 挂在news文件下的router实例


"""