# 导入datetime类，用于处理时间字段
from datetime import datetime
# 导入List类型注解，用于定义列表类型
from typing import List

# 导入Pydantic数据验证和序列化相关类
from pydantic import BaseModel, Field, ConfigDict

# 导入新闻基础信息模型
from TouTiaoApp.schemas.BaseNewsItem import NewsItemBase


# 定义添加浏览记录请求模型

class HistoryAddRequest(BaseModel):
    # 定义文章ID字段，必填
    newsId: int = Field(..., description="文章ID")


# 定义浏览记录项响应模型，继承自新闻基础信息模型

class HistoryNewItemResponse(NewsItemBase):
    # 配置Pydantic模型行为
    model_config = ConfigDict(
        # 允许通过别名填充字段
        populate_by_name=True,
        # 支持从ORM对象转换数据
        from_attributes=True
    )
    # 定义历史记录ID字段，使用别名historyId
    history_id: int = Field(alias="historyId")
    # 定义浏览时间字段，使用别名viewTime
    view_time: datetime = Field(alias="viewTime")


# 定义浏览记录列表响应模型

class HistoryListResponse(BaseModel):
    # 配置Pydantic模型行为
    model_config = ConfigDict(
        # 允许通过别名填充字段
        populate_by_name=True,
        # 支持从ORM对象转换数据
        from_attributes=True
    )
    # 定义浏览记录列表字段，默认为空列表
    list: List[HistoryNewItemResponse] = Field(default_factory=list, description="浏览记录列表")
    # 定义浏览记录总数字段，默认为0
    total: int = Field(default=0, description="浏览记录总数")
    # 定义是否有更多字段，默认为False
    hasMore: bool = Field(default=False, description="是否有更多")
