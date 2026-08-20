from datetime import datetime
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
from sqlalchemy.sql import functions


ASYNC_DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/fastapi_test?charset=utf8mb3"
# 1、创建数据库引擎
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=10,
    pool_recycle=3600,
)

# 1、定义数据库模型基类
class Base(DeclarativeBase):
    created_time: Mapped[datetime] = mapped_column(
        DateTime,
        insert_default=functions.now(),
        default=functions.now,
        comment="创建时间"
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime,
        insert_default=functions.now(),
        default=functions.now,
        onupdate=functions.now,
        comment="更新时间"
    )
# 2、定义数据库表字段.继承自Base
class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), comment="用户名")
    password: Mapped[str] = mapped_column(String(50), comment="密码")
    email: Mapped[str] = mapped_column(String(100), comment="邮箱")
    phone: Mapped[str] = mapped_column(String(11), comment="手机号")
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否激活")
    is_superuser: Mapped[bool] = mapped_column(default=False, comment="是否超级用户")
    is_deleted: Mapped[bool] = mapped_column(default=False, comment="是否删除")
    role_id: Mapped[int] = mapped_column(comment="角色ID")

#3、执行创建数据库表的操作
async def create_tables():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("数据库表创建成功")
    except Exception as e:
        print(f"数据库表创建失败: {e}")
        raise

# 4、定义应用的生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await create_tables()
    print("应用启动成功")
    yield
    # 关闭时执行
    await engine.dispose()
    print("应用关闭")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def read_root():
    return {"message": "Hello World"}



if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8000)



