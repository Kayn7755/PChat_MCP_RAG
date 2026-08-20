# 导入datetime类，用于处理时间字段
from datetime import datetime
# 导入SQLAlchemy字段类型和约束
from sqlalchemy import DateTime, UniqueConstraint, Index, Integer, String
# 导入SQLAlchemy ORM声明式基类和映射工具
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
# 导入SQLAlchemy内置函数
from sqlalchemy.sql import functions


# 定义ORM基类
# 通用字段
class Base(DeclarativeBase):
    # 定义创建时间字段，使用数据库服务器默认值
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=functions.now(),
        default=functions.now(),
        nullable=False,
        comment="创建时间"
    )


# 定义收藏表模型类
class Favorite(Base):
    # 指定数据库表名为"favorite"
    __tablename__ = "favorite"

    # 定义表的额外参数，如唯一约束和索引
    __table_args__ = (
        UniqueConstraint("user_id", "news_id",name="user_news_unique"), # UniqueConstraint唯一约束, 当前新闻只能收藏一次
        Index("fk_favorite_news_idx", "news_id"),
        Index("fk_favorite_user_idx", "user_id"),
    )
    # 定义收藏ID字段，作为主键并自动递增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="收藏ID")
    # 定义用户ID字段，必须唯一且不能为空
    user_id: Mapped[str] = mapped_column(Integer, nullable=False, unique=True, comment="分类名称")
    # 定义新闻ID字段，不能为空，默认为0
    news_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")

    # 定义对象的字符串表示方法，用于调试输出
    def __rapr__(self):
        return f"<favorite(id={self.id}, user_id={self.user_id}, news_id={self.news_id})>"