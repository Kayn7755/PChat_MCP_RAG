import uvicorn
from fastapi import FastAPI, Request

app = FastAPI()

# 先在代码里写的是内层
@app.middleware("http")
async def inner_middleware(request: Request, call_next):
    print("--> [进入] 内层中间件 B")
    response = await call_next(request)  # 传递给核心路由
    print("<-- [离开] 内层中间件 B")
    return response

# 后在代码里写的是外层
@app.middleware("http")
async def outer_middleware(request: Request, call_next):
    print("--> [进入] 外层中间件 A")
    response = await call_next(request)  # 传递给内层中间件 B
    print("<-- [离开] 外层中间件 A")
    return response

@app.get("/")
async def main():
    print("=== 执行核心路由处理 ===")
    return {"message": "Hello"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)