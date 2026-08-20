from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, Integer, String, Date, Float, func
from sqlalchemy import select
from fastapi import Depends

# 1.创建异步数据库引擎
engine = create_async_engine(
    "mysql+aiomysql://root:123456@localhost:3306/fastapi_test?charset=utf8mb3",
    echo=True,
    future=True,
    pool_size=10,  # 活跃的连接池
    max_overflow=20,  # 连接池最大数
    pool_timeout=10,  # 连接池超时时间
    pool_recycle=3600  # 连接池回收时间
)


# 2.定义模型类  创建时间和更新时间自动生成
# 2.定义模型类  创建时间和更新时间自动生成
class Base(DeclarativeBase):
    # 使用 server_default 告诉 MySQL 数据库在建表时加上默认值
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),  # <--- 关键修改点
        nullable=False,
        comment="创建时间"
    )

    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),  # <--- 关键修改点：数据库默认值
        onupdate=func.now(),  # 关键保留点：更新时让 SQLAlchemy 自动更新时间
        nullable=False,
        comment="更新时间"
    )


# 3.定义表
class Book(Base):
    # 定义表名
    __tablename__ = "books"
    # 定义字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, comment="书籍ID")
    auther: Mapped[str] = mapped_column(String(50), comment="作者")
    title: Mapped[str] = mapped_column(String(100), comment="书名")
    published_date: Mapped[datetime] = mapped_column(Date, comment="出版日期")
    price: Mapped[float] = mapped_column(Float, comment="价格")
    description: Mapped[str] = mapped_column(String(255), comment="描述")


# 4.获取数据库引擎
async def create_tables():
    # 首先获取数据库引擎
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# 使用 lifespan 替代 on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await create_tables()
    print("数据库表创建成功")
    yield
    # 关闭时执行（如果需要清理操作可以在这里添加）


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root():
    return {"message": "Hello World"}


# 5.创建数据库会话
Async_session = async_sessionmaker(
        bind=engine, # 绑定引擎
        class_=AsyncSession, # 使用的会话类
        expire_on_commit=False, # 提交后过期
        autocommit=False, # 自动提交
        autoflush=False # 自动刷新
)

# 6.创建查询依赖项
async def get_db():
    async with Async_session() as session:
        try:
            yield session
            await session.close()
            print("数据库会话已关闭")
        except Exception as e:
            print(f"数据库会话出错: {e}")
            await session.rollback()
            raise e
        finally:
            await session.close()
            print("数据库会话已关闭")

# 7.使用依赖项查询所有书籍数据
@app.get("/books")
async def get_books(db: AsyncSession = Depends(get_db)):
    # 查询所有书籍
    result = await db.execute(select(Book))
    books = result.scalars().all()
    return books

# 9.使用依赖项搜索书籍数据（必须在 /books/{book_id} 之前定义）
@app.get("/books/search_book")
async def search_book(db: AsyncSession = Depends(get_db)):
    # 模糊查询书籍
    result = await db.execute(select(Book).where(Book.title.like("%红%")))
    books = result.scalars().all()
    return books

# 10.使用依赖项进行AND查询（作者为'鲁迅'且价格大于30）
@app.get("/books/query_and")
async def query_and(db: AsyncSession = Depends(get_db)):
    # AND查询：作者为'鲁迅'且价格大于30
    result = await db.execute(select(Book).where(Book.auther == "鲁迅").where(Book.price > 30))
    books = result.scalars().all()
    return books

# 11.使用依赖项进行OR查询（作者为'鲁迅'或作者为'曹雪芹'）
@app.get("/books/query_or")
async def query_or(db: AsyncSession = Depends(get_db)):
    # OR查询：作者为'鲁迅'或作者为'曹雪芹'
    from sqlalchemy import or_
    result = await db.execute(select(Book).where(or_(Book.auther == "鲁迅", Book.auther == "曹雪芹")))
    books = result.scalars().all()
    return books

# 12.使用依赖项进行NOT查询（作者不为'鲁迅'）
@app.get("/books/query_not")
async def query_not(db: AsyncSession = Depends(get_db)):
    # NOT查询：作者不为'鲁迅'
    from sqlalchemy import not_
    result = await db.execute(select(Book).where(not_(Book.auther == "鲁迅")))
    books = result.scalars().all()
    return books

# 8.使用依赖项查询单本书籍数据
@app.get("/books/{book_id}")
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    # 查询单本书籍
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalars().first()
    return book


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
