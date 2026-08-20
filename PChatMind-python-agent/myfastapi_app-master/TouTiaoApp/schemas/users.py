# 从typing模块导入Optional类型注解表示字段可以为空
from typing import Optional

# 从Pydantic导入数据验证和序列化相关类
from pydantic import BaseModel, Field, ConfigDict


# 定义用户注册请求模型用于接收前端传来的注册数据
class UserRegisterLoginRequest(BaseModel):
    # 定义用户名字段必填的字符串类型
    username: str
    # 定义密码字段必填的字符串类型
    password: str

# 定义用户更新请求模型
class UserUpdateRequest(BaseModel):
    # 定义昵称字段可选
    nickname: Optional[str] = None
    # 定义个人简介字段可选
    bio: Optional[str] = None
    # 定义头像URL字段可选
    avatar: Optional[str] = None
    # 定义性别字段可选
    gender: Optional[str] = None
    # 定义手机号字段可选
    phone: Optional[str] = None

# 定义用户修改密码请求模型
class UserChangePasswordRequest(BaseModel):
    # 配置Pydantic模型行为
    model_config = ConfigDict(
        # 允许通过别名填充字段
        populate_by_name=True,
        # 支持从ORM对象如SQLAlchemy转换数据
        from_attributes=True
    )
    # 定义旧密码字段必填
    oldPassword: str = Field(...,description="旧密码")
    # 定义新密码字段必填且最小长度为6
    newPassword: str = Field(..., min_length=6,description="新密码")

# 定义用户基础信息模型包含可选的个人资料字段
class UserInfoBase(BaseModel):
    # 定义昵称字段可选最大长度50字符
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    # 定义个人简介字段可选最大长度500字符
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    # 定义头像URL字段可选（支持Base64，不限制长度）
    avatar: Optional[str] = Field(None, description="头像")
    # 定义性别字段可选最大长度10字符
    gender: Optional[str] = Field(None, max_length=10, description="性别")
    # 定义手机号字段可选最大长度11字符
    phone: Optional[str] = Field(None, max_length=11, description="手机号")


# 定义用户信息响应模型继承自UserInfoBase并添加必填字段
class UserInfoResponse(UserInfoBase):
    # 配置Pydantic模型的行为
    model_config = ConfigDict(
        # 允许通过别名填充字段
        populate_by_name=True,
        # 支持从ORM对象如SQLAlchemy转换数据
        from_attributes=True
    )
    # 定义用户ID字段必填的整数类型
    id: int
    # 定义用户名字段必填的字符串类型
    username: str


# 定义用户认证响应模型包含token和用户信息
class UserAuthResponse(BaseModel):
    # 配置Pydantic模型的行为
    model_config = ConfigDict(
        # 允许通过别名填充字段
        populate_by_name=True,
        # 支持从ORM对象如SQLAlchemy转换数据
        from_attributes=True
    )
    # 定义认证令牌字段必填的字符串类型
    token: str
    # 定义用户信息字段使用Field设置别名为userInfo 
    userInfo: UserInfoResponse = Field(..., alias="userInfo")