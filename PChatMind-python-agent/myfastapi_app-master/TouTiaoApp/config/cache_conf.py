"""
redis缓存配置模块
"""
# 导入Redis异步客户端类
import redis.asyncio as redis
# 导入Redis连接池类
from redis.asyncio import ConnectionPool
# 导入JSON序列化模块
import json
# 导入Optional类型注解
from typing import Optional, Any

# 定义Redis连接配置
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None  # 如果有密码请设置
REDIS_DECODE_RESPONSES = True  # 自动解码响应为字符串

# 定义默认缓存过期时间（秒）
DEFAULT_CACHE_TTL = 300  # 5分钟
NEWS_CACHE_TTL = 600  # 新闻缓存10分钟
USER_CACHE_TTL = 1800  # 用户缓存30分钟

# 创建Redis连接池
# 查询时直接用redis_client，他会从连接池中自动分配一个连接进行查询, 不会显示展示连接
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=REDIS_DECODE_RESPONSES,
    max_connections=20,
    retry_on_timeout=True,
    socket_keepalive=True,
) # redis_client是Redis客户端实例, 用于与Redis服务器进行交互; 内部会自带连接池

