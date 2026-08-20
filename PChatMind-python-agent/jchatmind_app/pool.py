"""
PostgreSQL 连接池管理：用 psycopg2 的连接池管理 PostgreSQL 连接，提高连接效率和稳定性。
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2 # Python连接PostgreSQL 数据库最流行的第三方库
from psycopg2.pool import SimpleConnectionPool # 导入pg数据库的连接池

logger = logging.getLogger(__name__)

_pool: SimpleConnectionPool | None = None


class DatabaseUnavailable(Exception):
    """连接池未建立（未启动 PostgreSQL 或未配置 DSN）。"""

    pass


def init_pool(dsn: str, minconn: int = 1, maxconn: int = 32) -> None:
    global _pool
    if _pool is not None:
        return
    _pool = SimpleConnectionPool(minconn, maxconn, dsn)


def try_init_pool(dsn: str, minconn: int = 1, maxconn: int = 32) -> bool:
    """尝试建立连接池；失败时返回 False 且不抛出异常。"""
    global _pool
    if _pool is not None:
        return True
    try:
        _pool = SimpleConnectionPool(minconn, maxconn, dsn)
        return True
    except psycopg2.OperationalError as e:
        logger.warning("PostgreSQL 连接失败: %s", e)
        _pool = None
        return False


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager # 获取一条数据库连接session
def connection() -> Generator[psycopg2.extensions.connection, None, None]:
    if _pool is None:
        raise DatabaseUnavailable(
            "PostgreSQL 未连接。请在本机启动 PostgreSQL、创建数据库 jchatmind（与 Java 版一致），"
            "并设置环境变量 JCHATMIND_DATABASE_URL，例如："
            "postgresql://postgres:你的密码@localhost:5432/jchatmind。"
            "若仅做前端联调可设 JCHATMIND_ALLOW_START_WITHOUT_DB=1 先启动服务。"
        )
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
