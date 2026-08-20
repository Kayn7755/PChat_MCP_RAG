# 导入SQLAlchemy ORM映射工具
from sqlalchemy.orm import Mapped, mapped_column,DeclarativeBase
# 导入SQLAlchemy字段类型和索引
from sqlalchemy import Integer, DateTime, ForeignKey, Index
# 导入datetime类
from datetime import datetime
# 导入用户和新闻模型
from .users import User
from .news import News


# 定义ORM基类

class Base(DeclarativeBase):
    pass


# 定义浏览历史表ORM模型

class History(Base):
    # 指定数据库表名为'history'
    __tablename__ = 'history'

    # 创建索引
    __table_args__ = (
        Index('fk_history_user_idx', 'user_id'),
        Index('fk_history_news_idx', 'news_id'),
        Index('idx_view_time', 'view_time'),
    )

    # 定义历史ID字段，作为主键并自动递增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="历史ID")
    # 定义用户ID字段，作为外键关联到User表
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id), nullable=False, comment="用户ID")
    # 定义新闻ID字段，作为外键关联到News表
    news_id: Mapped[int] = mapped_column(Integer, ForeignKey(News.id), nullable=False, comment="新闻ID")
    # 定义浏览时间字段，默认为当前时间
    view_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="浏览时间")


    # 定义对象的字符串表示方法
    def __repr__(self):
        return f"<History(id={self.id}, user_id={self.user_id}, news_id={self.news_id}, view_time={self.view_time})>"
