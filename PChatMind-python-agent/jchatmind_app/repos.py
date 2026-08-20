"""
数据访问层（Repository）：集中写 PostgreSQL 的 SQL CRUD，不负责 HTTP、也不做业务规则。
做什么
通过 pool.connection() 借连接，用 psycopg2 执行 CRUD，返回 dict 或 id。按表分块：

在分层里的位置
main.py（路由）→ biz.py（业务）→ repos.py（SQL）→ pool.py（连接）
表结构对照 init_db.sql。一句话：谁真正碰数据库、写 SQL，就是它；biz 决定「要不要删、怎么拼 VO」，repos 只负责「怎么读写表」。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from psycopg2.extras import RealDictCursor

from jchatmind_app.pool import connection


def _now() -> datetime:
    return datetime.now()


# --- agent ---
# 从数据库查出全部 Agent，按创建时间倒序返回
def agent_select_all() -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, name, description, system_prompt, model,
                   allowed_tools::text, allowed_kbs::text, chat_options::text,
                   created_at, updated_at
            FROM agent ORDER BY created_at DESC
            """
        ) # 用的就是原生 SQL 字符串，交给 psycopg2 执行
        # FastAPI/main.py 用的是 SQLAlchemy ORM / 查询构建器，不是手写完整 SQL
        return [dict(r) for r in cur.fetchall()] # 将查询结果转换为dict列表

# 从数据库查出指定id的Agent
def agent_select_by_id(aid: str) -> dict[str, Any] | None:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, name, description, system_prompt, model,
                   allowed_tools::text, allowed_kbs::text, chat_options::text,
                   created_at, updated_at
            FROM agent WHERE id = %s::uuid
            """,
            (aid,),
        ) # 参数化查询, 防止SQL注入
        row = cur.fetchone() # 从刚才 execute 的查询结果里取下一行（一条记录）。
        # fetchone() 取 1 条
        # fetchall() 取剩余全部，返回列表
        # fetchmany(n) 最多取 n 条
        return dict(row) if row else None

# 向数据库插入一条Agent
def agent_insert(row: dict[str, Any]) -> str:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent (name, description, system_prompt, model,
                allowed_tools, allowed_kbs, chat_options, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)
            RETURNING id::text
            """,
            (
                row["name"],
                row.get("description"),
                row.get("system_prompt"),
                row["model"],
                row["allowed_tools"],
                row["allowed_kbs"],
                row["chat_options"],
                row["created_at"],
                row["updated_at"],
            ), # INSERT 的入参；出参是下面的 fetchone()
        )
        return cur.fetchone()[0] # 返回插入的Agent的id

# 更新指定id的Agent  aid 要更新哪条 Agent，以及 fields改哪些字段「要更新的字段名 → 新值」
def agent_update(aid: str, fields: dict[str, Any]) -> bool:
    if not fields:
        return True
    sets: list[str] = []
    vals: list[Any] = []
    if "name" in fields:
        sets.append("name = %s")
        vals.append(fields["name"])
    if "description" in fields:
        sets.append("description = %s")
        vals.append(fields["description"])
    if "system_prompt" in fields:
        sets.append("system_prompt = %s")
        vals.append(fields["system_prompt"])
    if "model" in fields:
        sets.append("model = %s")
        vals.append(fields["model"])
    if "allowed_tools" in fields:
        sets.append("allowed_tools = %s::jsonb")
        vals.append(fields["allowed_tools"])
    if "allowed_kbs" in fields:
        sets.append("allowed_kbs = %s::jsonb")
        vals.append(fields["allowed_kbs"])
    if "chat_options" in fields:
        sets.append("chat_options = %s::jsonb")
        vals.append(fields["chat_options"])
    sets.append("updated_at = NOW()")
    vals.append(aid)
    sql = f"UPDATE agent SET {', '.join(sets)} WHERE id = %s::uuid"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, vals)
        return cur.rowcount > 0

# 删除指定id的Agent
def agent_delete(aid: str) -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM agent WHERE id = %s::uuid", (aid,))
        return cur.rowcount > 0
# 此处只负责删除, 前端刷新列表发现没有该agent后会自动删除该agent的会话和消息

# --- chat_session ---
# 从数据库查出全部会话，按更新时间倒序返回
def session_select_all() -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, agent_id::text, title, metadata::text, created_at, updated_at
            FROM chat_session ORDER BY updated_at DESC
            """
        )
        return [dict(r) for r in cur.fetchall()]

# 从数据库查出指定id的会话
def session_select_by_id(sid: str) -> dict[str, Any] | None:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, agent_id::text, title, metadata::text, created_at, updated_at
            FROM chat_session WHERE id = %s::uuid
            """,
            (sid,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

# 从数据库查出指定agent_id的会话，按更新时间倒序返回
def session_select_by_agent(agent_id: str) -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, agent_id::text, title, metadata::text, created_at, updated_at
            FROM chat_session WHERE agent_id = %s::uuid ORDER BY updated_at DESC
            """,
            (agent_id,),
        )
        return [dict(r) for r in cur.fetchall()]

# 向数据库插入一条会话
def session_insert(row: dict[str, Any]) -> str:
    meta = row.get("metadata")
    with connection() as conn, conn.cursor() as cur:
        if meta is None:
            cur.execute(
                """
                INSERT INTO chat_session (agent_id, title, metadata, created_at, updated_at)
                VALUES (%s::uuid,%s,NULL,%s,%s)
                RETURNING id::text
                """,
                (row["agent_id"], row.get("title"), row["created_at"], row["updated_at"]),
            )
        else:
            cur.execute(
                """
                INSERT INTO chat_session (agent_id, title, metadata, created_at, updated_at)
                VALUES (%s::uuid,%s,%s::jsonb,%s,%s)
                RETURNING id::text
                """,
                (row["agent_id"], row.get("title"), meta, row["created_at"], row["updated_at"]),
            )
        return cur.fetchone()[0]
# 此处只是插入, 前端刷新列表发现没有该会话后会自动删除该会话的消息

# 更新指定id的会话
def session_update(sid: str, fields: dict[str, Any]) -> bool:
    if not fields:
        return True
    sets: list[str] = []
    vals: list[Any] = []
    if "title" in fields:
        sets.append("title = %s")
        vals.append(fields["title"])
    if "metadata" in fields:
        sets.append("metadata = %s::jsonb")
        vals.append(fields["metadata"])
    sets.append("updated_at = NOW()")
    vals.append(sid)
    sql = f"UPDATE chat_session SET {', '.join(sets)} WHERE id = %s::uuid"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, vals)
        return cur.rowcount > 0

# 删除指定id的会话
def session_delete(sid: str) -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chat_session WHERE id = %s::uuid", (sid,))
        return cur.rowcount > 0


# --- chat_message ---
# 从数据库查出指定session_id的会话消息，按创建时间升序返回
def message_select_by_session(session_id: str) -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, session_id::text, role, content, metadata::text, created_at, updated_at
            FROM chat_message WHERE session_id = %s::uuid ORDER BY created_at ASC
            """,
            (session_id,),
        )
        return [dict(r) for r in cur.fetchall()]

# 从数据库查出指定session_id的会话消息，按创建时间降序返回
def message_select_by_session_recent(session_id: str, limit: int) -> list[dict[str, Any]]:
    """与 Java ChatMessageMapper.selectBySessionIdRecently 一致：ORDER BY created_at LIMIT。"""
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur: # 使用connection()函数获取数据库连接session
        cur.execute(
            """
            SELECT id::text, session_id::text, role, content, metadata::text, created_at, updated_at
            FROM chat_message WHERE session_id = %s::uuid
            ORDER BY created_at
            LIMIT %s
            """,
            (session_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]

# 从数据库查出指定id的会话消息
def message_select_by_id(mid: str) -> dict[str, Any] | None:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, session_id::text, role, content, metadata::text, created_at, updated_at
            FROM chat_message WHERE id = %s::uuid
            """,
            (mid,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

# 向数据库插入一条会话消息
def message_insert(session_id: str, role: str, content: str | None, metadata: Any) -> str:
    now = _now()
    with connection() as conn, conn.cursor() as cur:
        if metadata is None:
            cur.execute(
                """
                INSERT INTO chat_message (session_id, role, content, metadata, created_at, updated_at)
                VALUES (%s::uuid,%s,%s,NULL,%s,%s)
                RETURNING id::text
                """,
                (session_id, role, content, now, now),
            )
        else:
            cur.execute(
                """
                INSERT INTO chat_message (session_id, role, content, metadata, created_at, updated_at)
                VALUES (%s::uuid,%s,%s,%s::jsonb,%s,%s)
                RETURNING id::text
                """,
                (session_id, role, content, json.dumps(metadata), now, now),
            )
        return cur.fetchone()[0]

# 更新指定id的会话消息
def message_update(mid: str, content: str | None, metadata: Any) -> bool:
    sets: list[str] = []
    vals: list[Any] = []
    if content is not None:
        sets.append("content = %s")
        vals.append(content)
    if metadata is not None:
        sets.append("metadata = %s::jsonb")
        vals.append(json.dumps(metadata))
    if not sets:
        return True
    sets.append("updated_at = NOW()")
    vals.append(mid)
    sql = f"UPDATE chat_message SET {', '.join(sets)} WHERE id = %s::uuid"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, vals)
        return cur.rowcount > 0

# 删除指定id的会话消息
def message_delete(mid: str) -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chat_message WHERE id = %s::uuid", (mid,))
        return cur.rowcount > 0


# --- knowledge_base ---
# 从数据库查出全部知识库，按更新时间倒序返回
def kb_select_all() -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, name, description, metadata::text, created_at, updated_at
            FROM knowledge_base ORDER BY updated_at DESC
            """
        )
        return [dict(r) for r in cur.fetchall()]

# 从数据库查出指定id的知识库
def kb_select_by_id(kid: str) -> dict[str, Any] | None:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, name, description, metadata::text, created_at, updated_at
            FROM knowledge_base WHERE id = %s::uuid
            """,
            (kid,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

# 从数据库查出指定id的知识库列表
def kb_select_by_ids(ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    ph = ",".join(["%s::uuid"] * len(ids))
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT id::text, name, description, metadata::text, created_at, updated_at
            FROM knowledge_base WHERE id IN ({ph})
            """,
            tuple(ids),
        )
        return [dict(r) for r in cur.fetchall()]

# 向数据库插入一条知识库
def kb_insert(name: str, description: str | None) -> str:
    now = _now()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_base (name, description, metadata, created_at, updated_at)
            VALUES (%s,%s,NULL::jsonb,%s,%s)
            RETURNING id::text
            """,
            (name, description, now, now),
        )
        return cur.fetchone()[0]

# 更新指定id的知识库
def kb_update(kid: str, name: str | None, description: str | None) -> bool:
    sets: list[str] = []
    vals: list[Any] = []
    if name is not None:
        sets.append("name = %s")
        vals.append(name)
    if description is not None:
        sets.append("description = %s")
        vals.append(description)
    if not sets:
        return True
    sets.append("updated_at = NOW()")
    vals.append(kid)
    sql = f"UPDATE knowledge_base SET {', '.join(sets)} WHERE id = %s::uuid"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, vals)
        return cur.rowcount > 0

# 删除指定id的知识库
def kb_delete(kid: str) -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge_base WHERE id = %s::uuid", (kid,))
        return cur.rowcount > 0


# --- document ---
# 从数据库查出全部文档，按更新时间倒序返回
def doc_select_all() -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, kb_id::text, filename, filetype, size, metadata::text, created_at, updated_at
            FROM document ORDER BY updated_at DESC
            """
        )
        return [dict(r) for r in cur.fetchall()]

# 从数据库查出指定kb_id的文档，按更新时间倒序返回
def doc_select_by_kb(kb_id: str) -> list[dict[str, Any]]:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, kb_id::text, filename, filetype, size, metadata::text, created_at, updated_at
            FROM document WHERE kb_id = %s::uuid ORDER BY updated_at DESC
            """,
            (kb_id,),
        )
        return [dict(r) for r in cur.fetchall()]

# 从数据库查出指定id的文档
def doc_select_by_id(did: str) -> dict[str, Any] | None:
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text, kb_id::text, filename, filetype, size, metadata::text, created_at, updated_at
            FROM document WHERE id = %s::uuid
            """,
            (did,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

# 向数据库插入一条文档 只插入一条文档元数据记录 库里存的是「文档信息 + 分块向量」，不是整份 PDF 文件本身。
def doc_insert(row: dict[str, Any]) -> str:
    meta = row.get("metadata")
    with connection() as conn, conn.cursor() as cur:
        if meta is None:
            cur.execute(
                """
                INSERT INTO document (kb_id, filename, filetype, size, metadata, created_at, updated_at)
                VALUES (%s::uuid,%s,%s,%s,NULL,%s,%s)
                RETURNING id::text
                """,
                (
                    row["kb_id"],
                    row["filename"],
                    row["filetype"],
                    row["size"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO document (kb_id, filename, filetype, size, metadata, created_at, updated_at)
                VALUES (%s::uuid,%s,%s,%s,%s::jsonb,%s,%s)
                RETURNING id::text
                """,
                (
                    row["kb_id"],
                    row["filename"],
                    row["filetype"],
                    row["size"],
                    json.dumps(meta),
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        return cur.fetchone()[0]

# 更新指定id的文档
def doc_update(did: str, fields: dict[str, Any]) -> bool:
    if not fields:
        return True
    sets: list[str] = []
    vals: list[Any] = []
    for k, col in [("filename", "filename"), ("filetype", "filetype"), ("size", "size")]:
        if k in fields:
            sets.append(f"{col} = %s")
            vals.append(fields[k])
    if "metadata" in fields:
        sets.append("metadata = %s::jsonb")
        vals.append(json.dumps(fields["metadata"]))
    sets.append("updated_at = NOW()")
    vals.append(did)
    sql = f"UPDATE document SET {', '.join(sets)} WHERE id = %s::uuid"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, vals)
        return cur.rowcount > 0

# 删除指定id的文档
def doc_delete(did: str) -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM document WHERE id = %s::uuid", (did,))
        return cur.rowcount > 0


# --- chunk ---
# metadata是一段文本, chunk是文本的其中一块
# 向数据库插入一条分块 chunk（分块） 是：把文档切成一小段文本后，连同向量一起存进 chunk_bge_m3 表的一条记录，供 RAG 检索用
def chunk_insert(kb_id: str, doc_id: str, content: str, vector_literal: str) -> str:
    now = _now()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chunk_bge_m3 (kb_id, doc_id, content, metadata, embedding, created_at, updated_at)
            VALUES (%s::uuid,%s::uuid,%s,NULL::jsonb,%s::vector,%s,%s)
            RETURNING id::text
            """,
            (kb_id, doc_id, content, vector_literal, now, now),
        )
        return cur.fetchone()[0]

# 删除指定doc_id的所有分块
def chunk_delete_by_doc(doc_id: str) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chunk_bge_m3 WHERE doc_id = %s::uuid", (doc_id,))

"""
直接写sql与ORM的对比:
### 1. 裸 SQL（`repos.py` + psycopg2）

**优点**
- 直观：写什么 SQL 就执行什么，和 `init_db.sql`、pgvector 等能力对齐方便
- 依赖少、可控强：复杂查询、特殊类型（`::uuid`、`JSONB`、向量）好表达
- 性能路径短：少一层 ORM 抽象，排查 SQL 更容易

**缺点**
- 手写多：字段、条件、分页要自己拼，易写错
- 可移植性差：绑死 PostgreSQL 方言
- 无模型层：改表要手动改多处 SQL；类型安全弱（多是 `dict`）
- 连接/事务靠自己约定（本项目用 `connection()` 上下文）

### 2. ORM / Query API（SQLAlchemy + `Depends`）

**优点**
- Python 对象感强：`User.email`、关系、迁移（Alembic）更顺手
- 常见 CRUD、过滤、分页写起来快，防 SQL 注入也更省心（参数化默认好）
- 和 FastAPI 教程契合：`Depends(get_session)`、`response_model` 一条线
- 换数据库相对容易（仍有方言差异）

**缺点**
- 学习成本高：Session、lazy load、`scalars()` 等坑不少
- 复杂 SQL / 向量检索常要退回 `text()` 或原生 SQL
- 抽象层可能藏性能问题（N+1、多余查询）
- 项目更「重」：模型、引擎、session 工厂都要维护

### 怎么选（结合本项目）

| 场景 | 更合适 |
|------|--------|
| RAG、向量、大量自定义 SQL | 裸 SQL（本项目选择） |
| 常规业务 CRUD、团队熟悉 ORM | SQLAlchemy |
| 学习 FastAPI 官方风格 | ORM + Depends |
| 要对着表结构精调查询 | 裸 SQL 往往更直接 |

实际项目里常是**混合**：表映射用 ORM，复杂检索用裸 SQL。JChatMind 偏「薄仓库 + 手写 SQL」，你练习的 `FastAPI/main.py` 偏「教程式 ORM」。两种都能做好，看表复杂度和团队习惯。
"""