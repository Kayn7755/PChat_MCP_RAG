"""
FastAPI 自定义验证错误处理器完整示例

演示如何统一处理参数验证错误，返回友好的中文提示
"""

import uvicorn
from fastapi import FastAPI, Request, Query, Path
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI()


# ============================================
# 自定义验证错误处理器
# ============================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    自定义参数验证错误处理器
    
    当用户输入的参数不符合校验规则时，返回友好的中文提示
    """
    # 调试信息（可以删除）
    print("=" * 50)
    print("exc 对象:", exc)
    print("exc 类型:", type(exc))
    print("exc.errors() 返回值:", exc.errors())
    print("exc.errors() 类型:", type(exc.errors()))
    print("=" * 50)

    # 解析错误信息
    error_messages = []

    for error in exc.errors():
        field = error.get("loc", [])[-1]  # 字段名
        error_type = error.get("type", "")  # 错误类型
        input_value = error.get("input", "")  # 用户输入的值
        ctx = error.get("ctx", {})  # 上下文（限制值）

        # 根据错误类型返回中文提示
        if error_type == "less_than":
            limit = ctx.get("lt", "")
            error_messages.append(f"参数 '{field}' 的值 {input_value} 必须小于 {limit}")

        elif error_type == "greater_than":
            limit = ctx.get("gt", "")
            error_messages.append(f"参数 '{field}' 的值 {input_value} 必须大于 {limit}")

        elif error_type == "less_than_equal":
            limit = ctx.get("le", "")
            error_messages.append(f"参数 '{field}' 的值 {input_value} 必须小于或等于 {limit}")

        elif error_type == "greater_than_equal":
            limit = ctx.get("ge", "")
            error_messages.append(f"参数 '{field}' 的值 {input_value} 必须大于或等于 {limit}")

        elif error_type == "missing":
            error_messages.append(f"缺少必填参数 '{field}'")

        elif error_type == "int_parsing":
            error_messages.append(f"参数 '{field}' 的值 '{input_value}' 必须是有效的整数")

        elif error_type == "float_parsing":
            error_messages.append(f"参数 '{field}' 的值 '{input_value}' 必须是有效的数字")

        elif error_type == "string_too_short":
            min_len = ctx.get("min_length", "")
            error_messages.append(f"参数 '{field}' 的长度不能少于 {min_len} 个字符")

        elif error_type == "string_too_long":
            max_len = ctx.get("max_length", "")
            error_messages.append(f"参数 '{field}' 的长度不能超过 {max_len} 个字符")

        elif error_type == "value_error":
            error_msg = error.get("msg", "参数值错误")
            error_messages.append(f"参数 '{field}' {error_msg}")

        else:
            # 其他错误类型，使用默认消息
            error_messages.append(error.get("msg", "参数验证失败"))

    # 返回统一格式的错误响应
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "code": 422,
            "message": "参数验证失败",
            "data": {
                "errors": error_messages,
                "path": request.url.path
            }
        }
    )


# ============================================
# 数据模型
# ============================================

class UserCreate(BaseModel):
    """用户创建模型"""
    name: str = Field(..., description="用户名", min_length=2, max_length=20)
    age: int = Field(..., description="年龄", gt=0, lt=150)
    email: str = Field(..., description="邮箱")


# ============================================
# API 接口
# ============================================

@app.get("/")
async def read_root():
    """首页"""
    return {
        "message": "FastAPI 自定义验证错误处理器示例",
        "docs": "http://127.0.0.1:8000/docs",
        "test_endpoints": {
            "GET /api/users/abc": "测试整数解析错误",
            "GET /api/users/-1": "测试范围验证错误",
            "GET /api/items?name=A": "测试字符串长度错误",
            "POST /api/users": "测试请求体验证错误"
        }
    }


@app.get("/api/users/{user_id}")
async def get_user(user_id: int = Path(..., gt=0, le=100, description="用户ID")):
    """
    获取用户
    
    参数:
        user_id: 用户ID（必须在 1-100 之间）
    """
    return {"user_id": user_id, "name": "张三"}


@app.get("/api/items")
async def get_items(name: str = Query(..., min_length=3, max_length=50, description="商品名称")):
    """
    获取商品
    
    参数:
        name: 商品名称（3-50个字符）
    """
    return {"name": name, "price": 99.99}


@app.post("/api/users")
async def create_user(user: UserCreate):
    """
    创建用户
    
    请求体:
        name: 用户名（2-20个字符）
        age: 年龄（1-149）
        email: 邮箱
    """
    return {
        "message": "创建成功",
        "user": user
    }


# ============================================
# 启动配置
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("FastAPI 自定义验证错误处理器示例")
    print("=" * 60)
    print("访问 http://127.0.0.1:8000/docs 查看 API 文档")
    print("=" * 60)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
