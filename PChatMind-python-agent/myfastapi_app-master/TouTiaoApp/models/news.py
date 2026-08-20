"""
新闻模块用到的模型类
"""

# 从datetime模块导入日期时间类用于处理发布时间
from datetime import datetime
# 从SQLAlchemy导入各种字段类型和索引构造器
from sqlalchemy import DateTime, Integer, String, Index, Text, ForeignKey
# 从SQLAlchemy ORM模块导入声明式基类和映射工具
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
# 从SQLAlchemy SQL模块导入内置函数如now()
from sqlalchemy.sql import functions


# 定义ORM基类所有新闻相关模型都继承自此类
class Base(DeclarativeBase):
    # 定义创建时间字段记录数据插入的时间
    created_at: Mapped[datetime] = mapped_column(
        # 指定字段类型为DateTime
        DateTime,
        # 设置数据库层面的默认值为当前时间
        server_default=functions.now(),
        # 设置Python层面的默认值为当前时间
        default=functions.now(),
        # 添加字段注释说明
        comment="创建时间",
    )
    # 定义更新时间字段记录最后一次修改的时间
    updated_at: Mapped[datetime] = mapped_column(
        # 指定字段类型为DateTime
        DateTime,
        # 设置数据库层面的默认值为当前时间
        server_default=functions.now(),
        # 当记录更新时自动更新为当前时间
        onupdate=functions.now(),
        # 添加字段注释说明
        comment="更新时间",
    )


# 定义新闻分类表模型类
class Category(Base):
    # 指定数据库表名为news_category
    __tablename__ = "news_category"
    # 定义分类ID字段作为主键并自动递增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="分类ID")
    # 定义分类名称字段必须唯一且不能为空
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="分类名称")
    # 定义排序字段控制分类的显示顺序默认为0
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")

    # 定义对象的字符串表示方法用于调试输出
    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name}, sort_order={self.sort_order})>"


# 定义新闻表模型类
class News(Base):
    # 指定数据库表名为news
    __tablename__ = "news"
    # 定义表的额外参数如索引(此处是普通二级索引)
    __table_args__ = (
        # 为category_id字段创建索引加速按分类查询; fk_news_category_idx为索引名
        Index("fk_news_category_idx", "category_id"), # 高频查询场景
        # 为created_at字段创建索引加速按时间排序
        Index("fk_news_created_at_idx", "created_at") # 按发布时间排序
    ) # 创建索引, 提升查询速度
    # 定义新闻ID字段作为主键并自动递增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="新闻ID")
    # 定义新闻标题字段不能为空
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="标题")
    # 定义新闻描述字段用于简短摘要
    description: Mapped[str] = mapped_column(String(500), nullable=False, comment="描述")
    # 定义新闻正文字段使用Text类型存储长文本
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="内容")
    # 定义新闻图片URL字段
    image: Mapped[str] = mapped_column(String(255), nullable=False, comment="图片")
    # 定义新闻作者字段
    author: Mapped[str] = mapped_column(String(50), nullable=False, comment="作者")
    # 定义分类ID字段作为外键关联到news_category表
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("news_category.id"), nullable=False, comment="分类ID")
    # 定义浏览量字段默认为0
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="浏览量")
    # 定义发布时间字段默认为当前时间
    publish_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(), nullable=False, comment="发布时间")

    # 定义对象的字符串表示方法用于调试输出
    def __repr__(self):
        return f"<News(id={self.id}, title={self.title}, category_id={self.views})>"
"""
__table_args__
本质是：表级约束/索引的元组，最后可跟一个 dict 表选项
__table_args__ = (
    # 单列普通索引（当前写法）
    Index("fk_news_category_idx", "category_id"),

    # 联合索引（多列，常被叫“组合/联合索引”）
    Index("idx_cat_time", "category_id", "created_at"),

    # 唯一索引 / 唯一约束
    Index("uq_title", "title", unique=True),
    # UniqueConstraint("title", name="uq_title"),

    # 表级外键、检查约束等
    # ForeignKeyConstraint(...),
    # CheckConstraint("views >= 0"),

    # 最后这个 dict：表本身的参数
    {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "新闻表",
        # "schema": "news_app",
    },
)
"""