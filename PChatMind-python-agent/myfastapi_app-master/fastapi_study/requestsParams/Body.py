from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class User(BaseModel):
    """用户模型"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="用户名至少 3 位，至多 50 位",
        examples=["johndoe"],
        title="用户名"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=50,
        description="密码至少 8 位，至多 50 位",
        examples=["secret"],
        title="密码"
    )


@app.get("/")
async def read_root():
    """根路径"""
    return {"message": "Hello World"}


@app.post("/login/")
async def login(user: User):
    """
    用户登录接口
    
    参数:
        user: 用户对象，包含用户名和密码
        
    返回:
        dict: 包含用户名和密码的字典
    """
    return {"username": user.username, "password": user.password}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
