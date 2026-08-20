# 导入FastAPI的依赖注入和异常处理类
from fastapi import Depends, Header, HTTPException
# 导入SQLAlchemy异步会话类
from sqlalchemy.ext.asyncio import AsyncSession
# 导入HTTP状态码
from starlette import status

# 导入数据库会话依赖
from TouTiaoApp.config.db_conf import post_dbs
# 导入根据token获取用户的函数
from TouTiaoApp.curd.users import get_user_by_token
# 导入用户模型
from TouTiaoApp.models.users import User


# 定义获取当前用户的依赖注入函数
async def get_current_user(
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs),
        # 从请求头获取Authorization (Header从请求头中获取Authorization字段)
        Authorization: str = Header(..., description="Bearer <token>"), # ...表示必填, description="Bearer <token>"表示描述
) -> User:
    # 从Authorization头中提取token（移除"Bearer "前缀）
    Token = Authorization.replace("Bearer ", "")
    # 根据token查询用户
    user = await get_user_by_token(db, Token) # 如果token有效, 则返回用户对象, 否则返回None
    # 如果用户不存在，抛出401错误
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌或已过期")

    # 返回用户对象
    return user
    