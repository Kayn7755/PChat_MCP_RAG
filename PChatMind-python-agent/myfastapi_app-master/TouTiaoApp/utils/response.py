"""
封装统一成功响应格式
"""
# 导入FastAPI的JSON响应类，用于返回JSON格式数据
from fastapi.responses import JSONResponse
# 导入FastAPI的JSON编码器，用于将Python对象转换为JSON兼容格式
from fastapi.encoders import jsonable_encoder


# 定义成功响应函数，统一返回格式
# 将任何FastAPI,Pydantic, ORM对象都封装成code message data格式
def success_response(data=None, message="success"):
    # 构造响应内容字典
    content = {
        # 状态码，200表示成功
        "code": 200,
        # 提示信息，默认为"success"
        "message": message,
        # 实际数据，默认为None
        "data": data
    }
    # 使用jsonable_encoder处理数据（如datetime对象），并返回JSON响应
    return JSONResponse(content=jsonable_encoder(content))


# 定义失败响应函数，统一返回格式

def fail_response(code=500, msg="error", data=None):
    """
    失败响应函数
    
    参数：
    - code: 错误状态码（默认500）
    - msg: 错误提示信息（默认"error"）
    - data: 额外数据（可选）
    
    返回：
    - JSONResponse 对象
    """
    # 构造响应内容字典
    content = {
        # 错误状态码
        "code": code,
        # 错误提示信息
        "message": msg,
        # 额外数据（如果有）
        "data": data
    }
    # 使用jsonable_encoder处理数据，并返回JSON响应
    return JSONResponse(content=jsonable_encoder(content))