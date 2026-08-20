# 导入datetime类，用于处理时间字段
from datetime import datetime
# 导入List类型注解，用于定义列表类型
from typing import List

# 导入Pydantic数据验证和序列化相关类
from pydantic import BaseModel, ConfigDict, Field

# 导入新闻基础信息模型
from TouTiaoApp.schemas.BaseNewsItem import NewsItemBase


# 定义用户收藏创建请求模型

class FavoriteAddRequest(BaseModel):
    # 定义文章ID字段，必填
    newsId: int = Field(..., description="文章ID")


# 定义用户收藏状态响应模型

class FavoriteCheckResponse(BaseModel):
    # 配置Pydantic模型行为
    model_config = ConfigDict(
        # 允许通过别名填充字段
        populate_by_name=True,
        # 支持从ORM对象（如SQLAlchemy）转换数据
        from_attributes=True
    )
    # 定义是否收藏字段，必填
    isFavorite: bool = Field(..., description="是否收藏")


# 定义收藏新闻项响应模型，继承自新闻基础信息模型

class FavoriteNewsItemResponse(NewsItemBase):
    # 定义收藏ID字段，使用别名favoriteId
    favorite_id: int = Field(alias="favoriteId")
    # 定义收藏时间字段，使用别名favoriteTime
    favorite_time: datetime = Field(alias="favoriteTime")

    # 配置Pydantic模型行为
    model_config = ConfigDict(
        # 允许通过别名填充字段
        populate_by_name=True,
        # 支持从ORM对象转换数据
        from_attributes=True
    )


# 定义用户收藏列表响应模型

class FavoriteListResponse(BaseModel):
    # 配置Pydantic模型行为
    model_config = ConfigDict(
        # 允许通过别名填充字段
        populate_by_name=True,
        # 支持从ORM对象转换数据
        from_attributes=True
    )
    # 定义收藏列表字段，默认为空列表
    list: List[FavoriteNewsItemResponse] = Field(default_factory=list, description="收藏列表")
    # 定义收藏总数字段，默认为0
    total: int = Field(default=0, description="收藏总数")
    # 定义是否有更多字段，默认为False
    hasMore: bool = Field(default=False, description="是否有更多")
