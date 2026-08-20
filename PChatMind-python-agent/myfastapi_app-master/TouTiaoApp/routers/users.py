# 从FastAPI导入路由和依赖注入相关类
from fastapi import APIRouter, Depends
# 导入SQLAlchemy异步会话类型
from sqlalchemy.ext.asyncio import AsyncSession
# 导入Starlette状态码常量
from starlette import status
# 导入HTTP异常类
from starlette.exceptions import HTTPException

# 导入数据库会话依赖函数
from TouTiaoApp.config.db_conf import post_dbs
# 导入用户相关的CRUD操作函数
from TouTiaoApp.curd.users import get_user_by_username, create_user, create_user_token, authenticate_user
from TouTiaoApp.curd.users import update_user_info, change_password
# 导入用户请求和响应数据模式
from TouTiaoApp.schemas.users import UserRegisterLoginRequest, UserAuthResponse, UserInfoResponse, UserUpdateRequest, UserChangePasswordRequest
# 导入用户模型
from TouTiaoApp.models.users import User
# 导入获取当前用户的依赖函数
from TouTiaoApp.utils.auth import get_current_user

# 导入成功响应工具函数
from TouTiaoApp.utils.response import success_response

# 创建API路由器实例设置URL前缀为/api/user标签为users
router = APIRouter(prefix="/api/user", tags=["users"])


# 定义用户注册接口处理POST请求到/api/user/register, 接收请求体参数
@router.post("/register")
async def register(users_data: UserRegisterLoginRequest, db: AsyncSession = Depends(post_dbs)):
    # 根据用户名查询数据库中是否已存在该用户
    exist_user = await get_user_by_username(db, users_data.username)
    # 如果用户已存在则返回400错误
    if exist_user:
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    # 调用CRUD函数创建新用户密码会自动加密
    user = await create_user(db, users_data)

    # 为用户生成认证令牌token
    token = await create_user_token(db, user.id)
    # 使用Pydantic的model_validate将SQLAlchemy对象转换为响应模型
    response_data = UserAuthResponse(token=token, userInfo=UserInfoResponse.model_validate(user))
    # 返回统一格式的成功响应包含token和用户信息
    return success_response(data=response_data)


# 定义用户登录接口处理POST请求到/api/user/login
@router.post("/login")
async def login(users_data: UserRegisterLoginRequest, db: AsyncSession = Depends(post_dbs)):
    # 调用CRUD函数验证用户账号和密码
    user = await authenticate_user(db, users_data.username, users_data.password)
    # 如果验证失败则返回401错误
    if not user:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    # 为用户生成认证令牌token
    token = await create_user_token(db, user.id)
    # 构造响应数据包含token和用户信息
    response_data = UserAuthResponse(token=token, userInfo=UserInfoResponse.model_validate(user))
    # 返回统一格式的成功响应
    return success_response(data=response_data)


# 定义获取用户信息(用户登录后才能看信息)接口处理GET请求到/api/user/info 需要认证请求头和验证token
# 前端会携带token请求头, 后端会验证token(登陆时给token, 后续每次请求都会携带token)是否有效, 如果有效则返回用户信息, 否则返回401错误
@router.get("/info")
async def get_user_info(current_user: User = Depends(get_current_user)): # 此处通过依赖注入验证token并返回当前用户
    # 将ORM对象转换为响应模型自动过滤敏感字段
    user_info = UserInfoResponse.model_validate(current_user)
    # 返回统一格式的成功响应
    return success_response(data=user_info)


# 定义更新/修改用户信息接口处理PUT请求到/api/user/update
@router.put("/update")
async def update_user_info_route(
        # 接收用户更新请求数据
        user_data: UserUpdateRequest,
        # 注入当前用户
        current_user: User = Depends(get_current_user),
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs)
):
    # 调用CURD层更新用户信息（current_user 已经是 User 对象）
    updated_user = await update_user_info(db, current_user.username, user_data)
        
    # 转换为响应模型并返回
    return success_response(data=UserInfoResponse.model_validate(updated_user))

# 定义修改密码接口处理PUT请求到/api/user/password
@router.put("/password")
async def update_password(
        # 接收密码修改请求数据
        password_data: UserChangePasswordRequest,
        # 注入当前用户
        current_user: User = Depends(get_current_user),
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs)
):
    # 调用CRUD函数修改密码
    res_change_password = await change_password(db, current_user, password_data.oldPassword, password_data.newPassword)
    # 如果修改失败则返回500错误
    if not res_change_password:
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="修改密码失败")
    
    # 返回统一格式的成功响应
    return success_response(data=True)



    
