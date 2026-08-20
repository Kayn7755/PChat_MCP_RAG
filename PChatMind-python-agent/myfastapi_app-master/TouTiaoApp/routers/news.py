# API路由模块 - 新闻相关接口
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# 导入数据库会话依赖
from TouTiaoApp.config.db_conf import post_dbs
# 导入新闻CURD操作
from TouTiaoApp.curd import news
# 导入缓存操作函数
from TouTiaoApp.cache.news_cache import (
    get_categories_from_cache,
    set_categories_to_cache,
    get_news_list_from_cache,
    set_news_list_to_cache,
)
# 导入统一响应格式工具
from TouTiaoApp.utils.response import success_response

# 创建路由器，前缀为 /api/news(后续@router就可以省略前缀了)
router = APIRouter(prefix="/api/news", tags=["news"])

@router.get("/categories")
async def get_categories(
    db: AsyncSession = Depends(post_dbs),
    skip: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(10, ge=1, le=100, description="每页数量")
):
    """获取新闻分类列表 旁路缓存"""
    # 1. 尝试从缓存获取分类数据
    cached_categories = await get_categories_from_cache()
    if cached_categories is not None:
        # 缓存命中，直接返回
        return success_response(data=cached_categories)
    
    # 2. 缓存未命中，从数据库查询
    categories = await news.get_categories(db, skip, limit)
    
    # 3. 将查询结果存入缓存
    await set_categories_to_cache(categories)
    
    # 4. 返回分类数据
    return success_response(message="获取新闻分类成功", data=categories)

@router.get("/list")
async def get_news_list(
    db: AsyncSession = Depends(post_dbs), # 获取数据库会话, 通过依赖注入实现
    categoryId: int = Query(..., title="新闻分类ID", description="分类ID"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(..., ge=1, le=100, description="每页数量")
):
    """获取新闻列表（分页+缓存）"""
    """思路: 处理分页规则->查询新闻列表(数据库操作)->计算总量(数据库操作)->计算是否还有更多新闻"""
    # 1. 尝试从缓存获取新闻列表
    cached_list = await get_news_list_from_cache(categoryId, page, pageSize)
    if cached_list is not None:
        # 缓存命中，直接返回
        return success_response(data=cached_list)
    
    # 2. 缓存未命中，从数据库查询
    # 计算分页偏移量：(当前页-1) × 每页数量
    offset = (page - 1) * pageSize
    # 查询新闻列表
    news_list = await news.get_news_list(db, categoryId, offset, pageSize)
    # 统计该分类的新闻总数 通过聚合查询(不返回一行行原始数据，而是用函数把多行汇总成一个（或少量）结果。常见聚合函数：COUNT（计数）、SUM（求和）、AVG（平均）、MAX / MIN（最大/最小）。)
    total = await news.count_news_by_category(db, categoryId)
    # 判断是否有更多数据
    hasMore = total > offset + pageSize # hasMore 不参与后端再查库或改状态，只是算完塞进响应，给前端用
    
    # 3. 构造分页响应数据
    response_data = {
        "total": total,           # 新闻总数
        "page": page,             # 当前页码
        "pageSize": pageSize,     # 每页数量
        "list": news_list,        # 新闻列表
        "hasMore": hasMore        # 是否有更多数据
    }
    
    # 4. 将数据存入缓存（10分钟过期）
    await set_news_list_to_cache(categoryId, page, pageSize, response_data)
    
    # 5. 返回响应
    return success_response(message="获取新闻列表成功", data=response_data)

@router.get("/detail")
async def get_news_detail(
    db: AsyncSession = Depends(post_dbs),
    id: int = Query(..., title="新闻ID", description="新闻ID")
):
    """获取新闻详情（含浏览量统计和相关新闻）点击新闻后进入正文部分"""
    # 1. 查询新闻详情
    news_detail = await news.get_news_by_id(db, id)
    if not news_detail: # FastAPI异常处理
        # 新闻不存在，返回404 
        raise HTTPException(status_code=404, detail="新闻不存在")
    
    # 2. 增加新闻浏览量（+1）
    view_res = await news.increment_news_views(db, id)
    if not view_res:
        # 更新失败，返回500
        raise HTTPException(status_code=500, detail="更新新闻浏览量失败")
    
    # 3. 查询相关新闻（同分类的其他新闻，最多5条）
    relate_news = await news.get_related_news(db, id, news_detail.category_id, 5)
    
    # 4. 构造响应数据
    data = {
        "id": news_detail.id,              # 新闻ID
        "title": news_detail.title,        # 新闻标题
        "content": news_detail.content,    # 新闻内容
        "image": news_detail.image,        # 新闻图片URL
        "author": news_detail.author,      # 作者
        "publishTime": news_detail.publish_time,  # 发布时间
        "categoryId": news_detail.category_id,    # 分类ID
        "views": news_detail.views,        # 浏览量
        "relatedNews": relate_news         # 相关新闻列表
    }
    
    # 5. 返回响应
    return success_response(message="查看新闻详情成功", data=data)


