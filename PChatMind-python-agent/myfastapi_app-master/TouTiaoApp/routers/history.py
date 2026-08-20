# 导入FastAPI的路由和依赖注入相关类
from fastapi import APIRouter, Depends
# 导入SQLAlchemy异步会话类型
from sqlalchemy.ext.asyncio import AsyncSession

# 导入数据库会话依赖函数
from TouTiaoApp.config.db_conf import post_dbs
# 导入历史记录相关的CRUD操作函数
from TouTiaoApp.curd.history import add_history, get_user_history_list, remove_history, \
    clear_history
# 导入用户模型
from TouTiaoApp.models.users import User
# 导入历史记录请求和响应数据模式
from TouTiaoApp.schemas.history import HistoryAddRequest, HistoryListResponse, HistoryNewItemResponse
# 导入获取当前用户的依赖函数
from TouTiaoApp.utils.auth import get_current_user
# 导入成功响应工具函数
from TouTiaoApp.utils.response import success_response

# 创建API路由器实例，设置URL前缀为/api/history，标签为history
router = APIRouter(prefix="/api/history",tags=["history"])


# 定义添加浏览记录的POST接口

@router.post("/add")
async def add_user_history(
        # 接收添加历史记录请求数据
        data:HistoryAddRequest,
        # 注入当前用户
        user: User = Depends(get_current_user),
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs)
):
    # 调用CRUD函数添加历史记录
    data = await add_history(db, user.id, data.newsId)

    # 返回成功响应
    return success_response(message="添加浏览记录成功",data=data)


# 定义获取历史记录列表的GET接口

@router.get("/list")
async def get_history_list(
        # 接收页码参数，默认为1
        page: int = 1,
        # 接收每页数量参数，默认为10
        page_size: int = 10,
        # 注入当前用户
        user: User = Depends(get_current_user),
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs)
):
    # 调用CRUD函数获取历史记录列表
    rows, total = await get_user_history_list(db, user.id, page, page_size)
    # 判断是否有更多数据
    has_more = total > page * page_size

    # 将查询结果转换为响应模型（处理空数据情况）
    history_list = [
        HistoryNewItemResponse.model_validate({
            **news.__dict__,
            "view_time": view_time,
            "history_id": history_id
        }) for news, view_time, history_id in rows
    ] if rows else []

    # 构造响应数据
    data = HistoryListResponse(list=history_list, total=total, hasMore=has_more)

    # 返回成功响应
    return success_response(message="获取历史记录成功",data=data)


# 定义删除单条历史记录的DELETE接口

@router.delete("/delete/{history_id}")
async def delete_user_history(
        # 接收历史记录ID路径参数
        history_id: int,
        # 注入当前用户
        user: User = Depends(get_current_user),
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs)
):
    # 调用CRUD函数删除历史记录
    deleted = await remove_history(db, user.id, history_id)
    # 如果删除失败则返回404错误
    if not deleted:
        # 导入HTTP异常类
        from fastapi import HTTPException
        # 抛出404异常
        raise HTTPException(
            status_code=404,
            detail=f"未找到ID为{history_id}的浏览记录，请确认传入的是historyId而非newsId"
        )
    # 返回成功响应
    return success_response(message="删除历史记录成功", data={"deleted_id": history_id})
    

# 定义清空历史记录的DELETE接口

@router.delete("/clear")
async def clear_user_history(
    # 注入当前用户
    user: User = Depends(get_current_user),
    # 注入数据库会话
    db: AsyncSession = Depends(post_dbs)
):
    # 调用CRUD函数清空历史记录
    result = await clear_history(db, user.id)
    # 返回成功响应
    return success_response(message="清空历史记录成功", data={"deleted_count": result})