from fastapi import FastAPI, Depends
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData, Text, ForeignKey
from typing import Optional
from typing import List
from sqlalchemy import Integer, String, select # 核心模块导入常用的数据类型和操作函数
from sqlalchemy.orm import Mapped, mapped_column, relationship # 导入 SQLAlchemy 2.0 的核心类型映射工具

#         数据库  驱动(异步) 用户名:密码              数据库名
DU_URI = "mysql+aiomysql://root:root@127.0.0.1:3306/book_db?charset=utf8mb4"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 创建引擎
engine = create_async_engine(DU_URI,
                             echo=True, # 输出所有执行sql的日志
                             pool_size=10, # 连接池大小
                             max_overflow=2, # 允许连接池的最大连接数
                             pool_timeout=10, # 连接超时时间
                             pool_recycle=3600, # 连接回收时间
                             pool_pre_ping=True # 连接前检查
                             )

# 创建会话工厂
AsyncSessionFactory = sessionmaker(
    # Engine或者其子类对象（这里是AsyncEngine）
    bind=engine,
    # Session类的代替（默认是Session类）
    class_=AsyncSession,
    # 是否在查找之前执行flush操作（默认是True）
    autoflush=True,
    # 是否在执行commit操作后Session就过期（默认是True）
    expire_on_commit=False
)

# 定义命名约定的Base类
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        # ix: index，索引。
        "ix": 'ix_%(column_0_label)s',
        # un: unique，唯一约束
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        # ck: Check，检查约束
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        # fk: Foreign Key，外键约束
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        # pk: Primary Key，主键约束
        "pk": "pk_%(table_name)s"
    })


# 创建ORM模型, 不继承Base类就只是py类, 不会映射的数据库
class User(Base):
    __tablename__ = 'user' # 表名
    # Mapped 类型标注容器，告诉 IDE 和 Python 这个属性映射到了数据库的哪个类型。
    # mapped_column 用于指定字段的具体数据库属性（如主键、是否唯一、长度限制等）。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(200))

    # 必须与 UserExtension 中的 back_populates="user_extension" 对应
    user_extension: Mapped["UserExtension"] = relationship(back_populates="user", uselist=False)
    articles: Mapped[List["Article"]] = relationship(back_populates="author")

# 模型关系
# 和User模型一对一关系
# 将用户不常用的字段单独保存, 减少主表压力
class UserExtension(Base):
    __tablename__ = 'user_extension'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    university: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id")) # 外键, 引用user表中的id字段
    user: Mapped["User"] = relationship(back_populates="user_extension") # 定义表与表之间的 ORM 关联关系
    # user 不是数据库表里的普通字段（列），而是一个对象属性（类似指针或引用）。当你获取到一个 UserExtension 实例时，可以直接通过 extension.user 拿到与之关联的 User 对象。

