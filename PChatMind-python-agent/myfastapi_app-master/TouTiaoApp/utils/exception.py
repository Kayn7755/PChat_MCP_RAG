"""
封装全局异常处理器, 捕获业务中的异常
"""

# 导入traceback模块用于格式化异常信息
import traceback
# 从FastAPI导入HTTP异常和请求类
from fastapi import HTTPException, Request, FastAPI
# 导入JSON响应类
from fastapi.responses import JSONResponse
# 从SQLAlchemy导入数据库异常类
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
# 导入Starlette状态码常量
from starlette import status

# 定义调试模式开关开发模式返回详细错误信息
DEBUG_MODE = True


# 定义HTTP异常处理器(业务层面异常)
async def http_exception_handler(request: Request, exc: HTTPException):
    # HTTPException通常是业务逻辑主动抛出的data保持None
    return JSONResponse(
        # 设置HTTP状态码
        status_code=exc.status_code,
        # 构造响应内容
        content={
            # 返回错误码
            "code": exc.status_code,
            # 返回错误详情
            "message": exc.detail,
            # data字段为None
            "data": None
        }
    )


# 定义数据库完整性约束错误处理器
async def integrity_error_handler(request: Request, exc: IntegrityError):
    # 获取原始错误信息
    error_msg = str(exc.orig)

    # 判断具体的约束错误类型并进行语义化转换
    if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
        # 用户名重复错误
        detail = "用户名已存在"
    elif "FOREIGN KEY" in error_msg:
        # 外键约束错误
        detail = "关联数据不存在"
    else:
        # 其他约束错误
        detail = "数据约束冲突,请检查输入"

    # 开发模式下返回详细错误信息
    error_data = None
    if DEBUG_MODE: # 开发模式返回更详细错误类型
        error_data = {
            # 错误类型
            "error_type": "IntegrityError",
            # 错误详情
            "error_detail": error_msg,
            # 请求路径
            "path": str(request.url)
        }

    return JSONResponse(
        # 设置400状态码
        status_code=status.HTTP_400_BAD_REQUEST,
        # 构造响应内容
        content={
            # 返回错误码
            "code": 400,
            # 返回错误消息
            "message": detail,
            # 返回详细错误数据
            "data": error_data
        }
    )


# 定义SQLAlchemy数据库通用错误处理器
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    # 开发模式下返回详细错误信息
    error_data = None
    if DEBUG_MODE:
        error_data = {
            # 错误类型名称
            "error_type": type(exc).__name__,
            # 错误详情
            "error_detail": str(exc),
            # 异常堆栈跟踪
            "traceback": traceback.format_exc(),
            # 请求路径
            "path": str(request.url)
        }

    return JSONResponse(
        # 设置500状态码
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        # 构造响应内容
        content={
            # 返回错误码
            "code": 500,
            # 返回错误消息
            "message": "数据库操作失败,请稍后重试",
            # 返回详细错误数据
            "data": error_data
        }
    )


# 定义所有未捕获的其它通用异常处理器
async def general_exception_handler(request: Request, exc: Exception):
    # 开发模式下返回详细错误信息
    error_data = None
    if DEBUG_MODE:
        error_data = {
            # 错误类型名称
            "error_type": type(exc).__name__,
            # 错误详情
            "error_detail": str(exc),
            # 格式化异常信息为字符串方便日志记录和调试
            "traceback": traceback.format_exc(),
            # 请求路径
            "path": str(request.url)
        }

    return JSONResponse(
        # 设置500状态码
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        # 构造响应内容
        content={
            # 返回错误码
            "code": 500,
            # 返回错误消息
            "message": "服务器内部错误",
            # 返回详细错误数据
            "data": error_data
        }
    )


# 定义注册异常处理器的封装函数(传入FastAPI实例)
def register_exceptions(app: FastAPI):
    """子类在前, 父类在后"""
    # 将HTTP异常处理器注册到FastAPI实例
    app.add_exception_handler(HTTPException, http_exception_handler)
    # 将完整性错误处理器注册到FastAPI实例
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    # 将SQLAlchemy错误处理器注册到FastAPI实例
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    # 将通用异常处理器注册到FastAPI实例
    app.add_exception_handler(Exception, general_exception_handler)