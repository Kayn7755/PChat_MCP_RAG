"""
数据库配置
用异步引擎创建会话工厂
"""

# 从SQLAlchemy扩展模块导入异步数据库相关类
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 定义异步数据库连接URL，使用aiomysql驱动连接MySQL
# news_app指定库名
ASYNC_DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/news_app?charset=utf8mb3"

# 创建异步数据库引擎，用于管理数据库连接池
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,  # 启用SQL日志输出，便于调试
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# 创建异步会话工厂，用于生成数据库会话对象
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# 定义FastAPI依赖注入函数，用于获取数据库会话
async def post_dbs():
    # 使用上下文管理器创建并管理会话生命周期
    async with async_session() as session:
        try:
            # 将会话对象提供给路由函数使用
            yield session
            # 如果路由执行成功，提交事务到数据库
            await session.commit()
        except Exception as e:
            # 捕获异常并打印错误信息
            print(f"数据库异常: {e}")
            # 发生错误时回滚事务，保证数据一致性
            await session.rollback()
            # 重新抛出异常，让上层处理
            raise
        finally:
            # 无论成功或失败，最后都关闭会话释放资源
            await session.close()
