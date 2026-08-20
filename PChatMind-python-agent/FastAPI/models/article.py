from fastapi import FastAPI, Depends
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData, Text, ForeignKey
from typing import Optional, List
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

# Mapped[List["Tag"]]这才是真正声明多对多关系, 且必须加secondary告诉数据库这是一个多对多关系，需要通过中间表查
class Article(Base):
    __tablename__ = "article"
    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title:Mapped[str] = mapped_column(String(100))
    content:Mapped[str] = mapped_column(Text)

    author_id: Mapped[int] = mapped_column(Integer, ForeignKey('author.id'))
    author: Mapped["User"] = relationship(back_populates="articles")
    tags: Mapped[List["Tag"]] = relationship("Tag",
                                             back_populates="articles", # 只负责双向同步
                                             secondary="article_tag" # 将"article_tag"作为多对多的中间表
                                             )

# 和Article是多对多关系
class Tag(Base):
    __tablename__ = 'tag'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    articles: Mapped[list["Article"]] = relationship("Article", back_populates="tags",secondary="article_tag")

class ArticleTag(Base):
    __tablename__ = 'article_tag'
    id: Mapped[int] = mapped_column(Integer, ForeignKey("article.id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(String(100), primary_key=True)

async def get_session():
    session = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()
