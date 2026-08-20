# 导入SQLAlchemy查询构造器和聚合函数
from sqlalchemy import func, select, delete
# 导入SQLAlchemy异步会话类
from sqlalchemy.ext.asyncio import AsyncSession

# 导入历史记录和新闻模型
from TouTiaoApp.models.history import History
from TouTiaoApp.models.news import News


# 定义添加浏览记录的函数
async def add_history(db: AsyncSession, user_id: int, news_id: int):
    # 创建历史记录对象
    history = History(user_id=user_id, news_id=news_id)
    # 将对象添加到会话
    db.add(history)
    # 提交事务
    await db.commit()
    # 刷新对象以获取最新数据
    await db.refresh(history)
    # 返回添加的历史记录
    return history


# 定义获取历史记录列表的函数
async def get_user_history_list(
        # 数据库会话
        db: AsyncSession,
        # 用户ID
        user_id: int,
        # 页码
        page: int,
        # 每页数量
        page_size: int
):
    # 构造查询总数的SQL语句
    count_query = select(func.count(History.id)).where(History.user_id == user_id)
    # 执行查询
    result = await db.execute(count_query)
    # 获取总数如果为None则返回0
    total = result.scalars().first() or 0

    # 计算偏移量
    offset = (page - 1) * page_size
    # 构造分页查询语句
    query = (select(News,History.view_time.label("history_time"),History.id.label("history_id"))
            .join(History, History.news_id == News.id)
            .where(History.user_id == user_id)
            .order_by(History.view_time.desc())
            .offset(offset).limit(page_size)
            )
    # 执行查询
    result = await db.execute(query)
    # 获取所有结果
    rows = result.all()
    # 返回结果和总数
    return rows, total


# 定义删除单条历史记录的函数
async def remove_history(db: AsyncSession, user_id: int, history_id: int):
    # 先检查记录是否存在
    from sqlalchemy import select
    # 构造查询语句
    check_stmt = select(History).where(History.user_id == user_id, History.id == history_id)
    # 执行查询
    check_result = await db.execute(check_stmt)
    # 获取记录
    existing_record = check_result.scalar_one_or_none()
    
    # 如果记录不存在
    if not existing_record:
        # 打印调试信息
        print(f"记录不存在: user_id={user_id}, history_id={history_id}")
        # 查询该用户所有记录
        all_stmt = select(History.id).where(History.user_id == user_id)
        # 执行查询
        all_result = await db.execute(all_stmt)
        # 获取所有ID
        all_ids = [row[0] for row in all_result.all()]
        # 打印所有ID
        print(f"用户{user_id}的所有history_id: {all_ids}")
        # 返回False
        return False
    
    # 执行删除
    # 构造删除语句
    stmt = delete(History).where(History.user_id == user_id, History.id == history_id)
    # 执行删除
    result = await db.execute(stmt)
    # 提交事务
    await db.commit()
    # 获取影响行数
    deleted_count = result.rowcount
    # 打印删除结果
    print(f"删除结果: user_id={user_id}, history_id={history_id}, 影响行数={deleted_count}")
    # 返回是否删除成功
    return deleted_count > 0


# 定义清空历史记录的函数
async def clear_history(db: AsyncSession, user_id: int):
    # 构造删除语句
    query = delete(History).where(History.user_id == user_id)
    # 执行删除
    result = await db.execute(query)
    # 提交事务
    await db.commit()

    # 返回删除的记录数
    return result.rowcount or 0

