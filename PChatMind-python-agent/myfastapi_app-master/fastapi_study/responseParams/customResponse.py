import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Optional

app = FastAPI()


class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    name: str
    age: int
    email: Optional[str] = None
    created_at: str


class APIResponse(BaseModel):
    """API 响应包装"""
    success: bool
    code: int
    message: str
    data: Optional[UserResponse] = None


@app.get("/api/pydantic/user/{user_id}", response_model=APIResponse)
async def get_user_with_model(user_id: int):
    """
    使用 Pydantic 模型规范返回格式

    response_model 会自动验证和格式化返回数据
    """
    user = UserResponse(
        id=user_id,
        name="张三",
        age=25,
        email="zhangsan@example.com",
        created_at="2024-01-01 12:00:00"
    )

    return {
        "success": True,
        "code": 200,
        "message": "获取成功",
        "data": user
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
