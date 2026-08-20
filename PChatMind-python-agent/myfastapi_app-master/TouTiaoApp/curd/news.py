# 从SQLAlchemy导入查询构造器和聚合函数
from sqlalchemy import select, func, update
# 导入异步会话类型注解
from sqlalchemy.ext.asyncio import AsyncSession
# 导入新闻数据模型（Category和News）
from TouTiaoApp.models.news import *


# 获取新闻分类列表的函数
async def get_categories(db: AsyncSession, skip: int, limit: int):
    # 构造SELECT查询语句，设置偏移量和限制数量
    stmt = select(Category).offset(skip).limit(limit)
    # 执行查询并等待结果
    result = await db.execute(stmt)
    # 获取所有查询结果并返回
    return result.scalars().all()


# 获取指定分类的新闻列表的函数
#                       传入数据库session  查询的id          跳过的数量  每页展示数 
async def get_news_list(db: AsyncSession, category_id: int, skip: int, limit: int):
    # 构造SELECT查询语句，筛选指定分类的新闻，并设置分页
    #                         查询指定新闻                      设置跳过数量       指定每页数量
    stmt = select(News).where(News.category_id == category_id).offset(skip).limit(limit)
    # 执行查询并等待结果
    result = await db.execute(stmt)
    # 获取所有查询结果并返回
    return result.scalars().all()


# 统计指定分类新闻数量的函数
async def count_news_by_category(db: AsyncSession, category_id: int):
    # 构造COUNT聚合查询，统计指定分类的新闻数量
    stmt = select(func.count(News.id)).where(News.category_id == category_id)
    # 执行查询并等待结果
    result = await db.execute(stmt)
    # 获取单个聚合值并返回
    return result.scalar_one()


# 获取新闻详情的函数
async def get_news_by_id(db: AsyncSession, news_id: int):
    # 构造SELECT查询语句，筛选指定ID的新闻
    stmt = select(News).where(News.id == news_id)
    # 执行查询并等待结果
    result = await db.execute(stmt)
    # 获取查询结果的第一条记录并返回
    return result.scalars().first()


# 增加新闻浏览量的函数
async def increment_news_views(db: AsyncSession, news_id: int):
    # 构造UPDATE语句，将指定新闻的views字段加1
    stmt = update(News).where(News.id == news_id).values(views=News.views + 1)
    # 执行更新操作并等待结果
    result = await db.execute(stmt)
    # 提交事务，使更新生效
    await db.commit()
    # 判断受影响的行数，大于0表示更新成功
    return result.rowcount > 0 # 执行数据库更新操作时, 要检查是否真的命中了数据
# 改成停留三秒后再+1: 改成「前端满 3 秒再调独立上报接口」。


# 获取相关新闻列表的函数 按浏览量排序
async def get_related_news(db: AsyncSession, news_id: int, category_id: int, limit: int = 5):
    # 构造SELECT查询语句，排除当前新闻并筛选同分类，按浏览量和发布时间降序排序(News.id != news_id不包括自己)
    stmt = select(News).where(News.id != news_id, News.category_id == category_id).order_by(
        News.views.desc(), News.publish_time.desc()
    ).limit(limit)
    # 执行查询并等待结果
    result = await db.execute(stmt)
    # 获取所有相关新闅对象
    related_news = result.scalars().all()
    # 使用列表推导式将News对象转换为字典格式
    return [
        {
            # 提取新闻ID
            "id": news_detail.id,
            # 提取新闻标题
            "title": news_detail.title,
            # 提取新闻内容
            "content": news_detail.content,
            # 提取新闻图片URL
            "image": news_detail.image,
            # 提取新闻作者
            "author": news_detail.author,
            # 提取发布时间
            "publishTime": news_detail.publish_time,
            # 提取分类ID
            "categoryId": news_detail.category_id,
            # 提取浏览量
            "views": news_detail.views
        }
        # 遍历所有相关新闻对象
        for news_detail in related_news
    ]
