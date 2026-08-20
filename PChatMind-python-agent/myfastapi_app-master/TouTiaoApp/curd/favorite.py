# 导入SQLAlchemy查询构造器和聚合函数
from sqlalchemy import select, delete, func
# 导入SQLAlchemy异步会话类
from sqlalchemy.ext.asyncio import AsyncSession

# 导入收藏和新闻模型
from TouTiaoApp.models.favorite import Favorite
from TouTiaoApp.models.news import News


# 定义判断用户是否收藏了新闻的函数
async def check_favorite_exists(db: AsyncSession, user_id: int, news_id: int):
    # 构造查询语句
    query = select(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    # 执行查询
    result = await db.execute(query)
    # 返回是否存在
    return result.scalar_one_or_none() is not None


# 定义添加收藏的函数
async def add_favorite(db: AsyncSession, user_id: int, news_id: int):
    # 创建收藏对象
    favorite = Favorite(user_id=user_id, news_id=news_id)
    # 将对象添加到会话
    db.add(favorite)
    # 提交事务
    await db.commit()
    # 刷新对象以获取最新数据
    await db.refresh(favorite)
    # 返回添加的收藏
    return favorite


# 定义取消收藏的函数
async def remove_favorite(db: AsyncSession, user_id: int, news_id: int):
    # 构造删除语句
    stmt = delete(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    # 执行删除
    result = await db.execute(stmt)
    # 返回是否删除成功
    return  result.rowcount > 0


# 定义获取收藏列表的函数
async def get_favorite_list(db: AsyncSession, user_id: int, page: int = 1, size: int = 10):
    # 构造查询总数的SQL语句
    count_query = select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
    # 执行查询
    result = await db.execute(count_query)
    # 获取总数如果为None则返回0
    total = result.scalars().first() or 0

    # 计算偏移量
    offset = (page - 1) * size
    # 构造分页查询语句
    query = (select(News,Favorite.created_at.label("favorite_time"),Favorite.id.label("favorite_id"))
             .join(Favorite, Favorite.news_id == News.id)
             .where(Favorite.user_id == user_id)
             .order_by(Favorite.created_at.desc())
             .offset(offset).limit(size)
             )
    # 执行查询
    result = await db.execute(query)
    # 获取所有结果
    all_results = result.all()

    # 返回结果和总数
    return all_results, total


# 定义清空当前用户收藏列表的函数
async def clear_favorites(db: AsyncSession, user_id: int):
    # 构造删除语句
    stmt = delete(Favorite).where(Favorite.user_id == user_id)
    # 执行删除
    result = await db.execute(stmt)
    # 提交事务
    await db.commit()
    # 返回是否删除成功
    return result.rowcount > 0


