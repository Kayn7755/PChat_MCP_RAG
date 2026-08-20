# 导入FastAPI的路由、依赖注入和查询参数相关类
from fastapi import APIRouter, Depends, Query, HTTPException
# 导入SQLAlchemy异步会话类型
from sqlalchemy.ext.asyncio import AsyncSession

# 导入数据库会话依赖函数
from TouTiaoApp.config.db_conf import post_dbs
# 导入收藏相关的CRUD操作函数
from TouTiaoApp.curd.favorite import check_favorite_exists, remove_favorite, get_favorite_list, \
    clear_favorites, add_favorite
# 导入用户模型
from TouTiaoApp.models.users import User
# 导入收藏请求和响应数据模式
from TouTiaoApp.schemas.favorite import FavoriteCheckResponse, FavoriteAddRequest, FavoriteListResponse, FavoriteNewsItemResponse
# 导入获取当前用户的依赖函数
from TouTiaoApp.utils.auth import get_current_user
# 导入成功响应工具函数
from TouTiaoApp.utils.response import success_response

# 创建API路由器实例，设置URL前缀为/api/favorite，标签为favorite
router = APIRouter(prefix="/api/favorite", tags=["favorite"])


# 定义检查是否已收藏的GET接口 需要认证请求头和验证token
@router.get("/check")
async def check_favorite(
        # 接收文章ID查询参数，必填
        newsId: int = Query(..., alias="newsId", description="文章ID"), # alias="newsId"表示将查询参数映射为newsId
        # 注入当前用户
        user: User = Depends(get_current_user), # 此处通过依赖注入验证token并返回当前用户
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs),

):
    # 查询是否已收藏
    is_favorite = await check_favorite_exists(db, user.id, newsId)
    # 返回查询结果
    return success_response(data=FavoriteCheckResponse(isFavorite=is_favorite), message="查询成功")


# 定义添加收藏的POST接口
@router.post("/add")
async def add_user_favorite(
        # 接收收藏请求数据
        data: FavoriteAddRequest, # 接收请求体参数(json格式)
        # 注入当前用户
        user: User = Depends(get_current_user),
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs),

):
    # 调用CRUD函数添加收藏
    result = await add_favorite(db, user.id, data.newsId)
    # 返回成功响应
    return success_response(data=result, message="收藏成功")


# 定义取消收藏的DELETE接口
@router.delete("/remove")
async def remove_user_favorite(
        # 接收文章ID查询参数，必填
        newsId: int = Query(..., description="文章ID"),
        # 注入当前用户
        user: User = Depends(get_current_user),
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs),
):
    # 调用CRUD函数取消收藏
    result = await remove_favorite(db, user.id, newsId)
    # 如果取消失败则返回404错误
    if not result:
        return HTTPException(status_code=404, detail="无收藏结果")
    # 返回成功响应
    return success_response(data=result, message="取消收藏成功")


# 定义获取收藏列表的GET接口 涉及指定页码查询和分页
@router.get("/list")
async def get_user_favorite_list(
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs),
        # 注入当前用户
        user: User = Depends(get_current_user),
        # 接收页码参数，默认为1
        page: int = Query(1, description="页码"),
        # 接收每页数量参数，默认为10
        page_size: int = Query(10, description="每页数量"),
):
    # 调用CRUD函数获取收藏列表
    all_results, total = await get_favorite_list(db, user.id, page, page_size) # all_results是查询第page页的结果列表, total是总数量
    # 将查询结果转换为响应模型
    favorite_list = [
        FavoriteNewsItemResponse.model_validate({
            **news.__dict__,
            "favorite_time": favorite_time,
            "favorite_id": favorite_id
        }) for news, favorite_time, favorite_id in all_results
    ]
    # 判断是否有更多数据
    has_more = total > page * page_size
    # 构造响应数据
    data = FavoriteListResponse(list=favorite_list, total=total, hasMore=has_more)
    # 返回成功响应
    return success_response(data=data, message="获取收藏列表成功")


# 定义清空收藏的DELETE接口
@router.delete("/clear")
async def clear_user_favorites(
        # 注入当前用户
        user: User = Depends(get_current_user),
        # 注入数据库会话
        db: AsyncSession = Depends(post_dbs),
):
    # 调用CRUD函数清空收藏
    data = await clear_favorites(db, user.id)
    # 返回成功响应
    return success_response(data=data, message="清空收藏列表成功")