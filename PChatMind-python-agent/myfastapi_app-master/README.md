# Toutiao App API 接口规范文档

## 项目概述

Toutiao App 是一个基于 FastAPI + Vue3 的全栈新闻资讯平台，提供新闻浏览、用户认证、收藏管理、历史记录和 AI 智能问答等功能。项目采用前后端分离架构，后端使用 Python FastAPI 框架，前端使用 Vue3 + Vite 构建。

### 核心功能

- ✅ **用户系统**: 注册、登录、个人信息管理、头像上传（Base64）
- ✅ **新闻浏览**: 分类浏览、分页加载、详情查看
- ✅ **收藏管理**: 添加收藏、取消收藏、收藏列表
- ✅ **历史记录**: 浏览记录、历史记录管理
- ✅ **AI 问答**: 智能对话、流式响应
- ✅ **智能导航**: 相关推荐跳转、返回分类首页

---

## 技术栈

### 后端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | >=3.11 | 编程语言 |
| **FastAPI** | >=0.136.1 | Web 框架，高性能异步 API |
| **SQLAlchemy** | >=2.0.49 | ORM 数据库操作框架 |
| **aiomysql** | >=0.3.2 | MySQL 异步驱动 |
| **Redis** | >=7.4.0 | 缓存系统，提升数据读取性能 |
| **Uvicorn** | >=0.46.0 | ASGI 服务器，运行 FastAPI 应用 |
| **Passlib[bcrypt]** | 1.7.4 | 密码加密与验证 |
| **Cryptography** | >=47.0.0 | 加密算法支持 |
| **HTTPX** | >=0.28.1 | 异步 HTTP 客户端，用于 AI 接口调用 |

### 前端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| **Vue** | ^3.x | 前端渐进式框架 |
| **Vite** | ^7.1.6 | 前端构建工具 |
| **Vue Router** | ^4.5.1 | 路由管理 |
| **Pinia** | ^3.0.3 | 状态管理 |
| **Pinia PersistedState** | ^4.5.0 | Pinia 持久化插件 |
| **Vant** | ^4.9.21 | 移动端 UI 组件库 |
| **Axios** | ^1.12.2 | HTTP 请求库 |
| **Vue I18n** | ^9.8.0 | 国际化支持 |
| **Marked** | ^16.3.0 | Markdown 解析器 |
| **DOMPurify** | ^3.2.7 | HTML 内容安全过滤 |

---

## 项目结构

```
myfastapi_app/
├── TouTiaoApp/              # 后端项目根目录
│   ├── main.py               # FastAPI 应用入口（含日志中间件、SSE流式处理）
│   ├── config/               # 配置模块
│   │   ├── db_conf.py        # 数据库配置（MySQL）
│   │   ├── cache_conf.py     # Redis 缓存配置
│   │   └── ai_conf.py        # AI 服务配置
│   ├── models/               # SQLAlchemy 数据模型
│   │   ├── users.py          # 用户和令牌模型
│   │   ├── news.py           # 新闻和分类模型
│   │   ├── favorite.py       # 收藏记录模型
│   │   └── history.py        # 浏览历史模型
│   ├── schemas/              # Pydantic 数据验证模式
│   │   ├── users.py          # 用户请求/响应模式
│   │   ├── BaseNewsItem.py   # 新闻基础模式
│   │   ├── favorite.py       # 收藏相关模式
│   │   └── history.py        # 历史记录相关模式
│   ├── curd/                 # 数据库 CRUD 操作层
│   │   ├── users.py          # 用户增删改查
│   │   ├── news.py           # 新闻增删改查
│   │   ├── favorite.py       # 收藏操作
│   │   └── history.py        # 历史记录操作
│   ├── routers/              # API 路由层
│   │   ├── users.py          # 用户相关接口
│   │   ├── news.py           # 新闻相关接口
│   │   ├── favorite.py       # 收藏相关接口
│   │   ├── history.py        # 历史记录接口
│   │   └── ai_chat.py        # AI 问答接口
│   ├── cache/                # 缓存操作层
│   │   └── news_cache.py     # 新闻缓存逻辑
│   ├── utils/                # 工具函数
│   │   ├── auth.py           # JWT Token 认证
│   │   ├── security.py       # 密码加密/验证
│   │   ├── response.py       # 统一响应格式
│   │   ├── exception.py      # 全局异常处理
│   │   └── log_utils.py      # API 日志工具
│   └── __init__.py
│
├── xwzx-news/                # 前端项目根目录
│   ├── src/
│   │   ├── views/            # 页面组件
│   │   │   ├── Home.vue      # 首页（分类切换、新闻列表）
│   │   │   ├── NewsDetail.vue # 新闻详情（收藏、相关推荐、返回优化）
│   │   │   ├── Category.vue  # 分类页
│   │   │   ├── Login.vue     # 登录页
│   │   │   ├── Register.vue  # 注册页
│   │   │   ├── Favorite.vue  # 收藏页
│   │   │   ├── History.vue   # 历史页
│   │   │   ├── AIChat.vue    # AI 问答页（流式响应）
│   │   │   ├── My.vue        # 个人中心（头像动态显示）
│   │   │   ├── Profile.vue   # 个人资料（头像上传Base64）
│   │   │   └── Settings.vue  # 设置页
│   │   ├── components/       # 公共组件
│   │   │   ├── TabBar.vue    # 底部导航栏
│   │   │   ├── NewsItem.vue  # 新闻列表项
│   │   │   └── HelloWorld.vue # 示例组件
│   │   ├── store/            # Pinia 状态管理
│   │   │   ├── user.js       # 用户状态
│   │   │   ├── news.js       # 新闻状态
│   │   │   ├── favorite.js   # 收藏状态
│   │   │   ├── history.js    # 历史状态
│   │   │   ├── theme.js      # 主题状态
│   │   │   ├── language.js   # 语言状态
│   │   │   └── index.js      # Store 入口
│   │   ├── router/           # 路由配置
│   │   ├── i18n/             # 国际化配置
│   │   ├── config/           # 前端配置
│   │   │   └── api.js        # API 地址配置
│   │   ├── App.vue           # 根组件
│   │   ├── main.js           # 入口文件
│   │   └── style.css         # 全局样式
│   ├── package.json          # 依赖配置
│   └── vite.config.js        # Vite 配置
│
├── pyproject.toml            # Python 项目配置
└── uv.lock                   # 依赖锁定文件
```

---

## 数据库设计

### MySQL 表结构

#### 1. 用户表 (user)

```sql
CREATE TABLE user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    nickname VARCHAR(50),
    avatar TEXT DEFAULT 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg',
    gender ENUM('male', 'female', 'unknown') DEFAULT 'unknown',
    bio VARCHAR(500) DEFAULT '这个人很懒,什么也没留下',
    phone VARCHAR(20) UNIQUE,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    INDEX username_UNIQUE (username),
    INDEX phone_UNIQUE (phone)
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 用户 ID（自增主键） |
| username | VARCHAR(50) | 用户名（唯一） |
| password | VARCHAR(255) | 密码（bcrypt加密） |
| nickname | VARCHAR(50) | 昵称（可选） |
| avatar | TEXT | 头像 URL 或 Base64 编码（支持长文本） |
| gender | ENUM | 性别（male/female/unknown） |
| bio | VARCHAR(500) | 个人简介（可选） |
| phone | VARCHAR(20) | 手机号（唯一，可选） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### 2. 用户令牌表 (user_token)

```sql
CREATE TABLE user_token (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX token_UNIQUE (token),
    INDEX fk_user_token_idx (user_id)
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 令牌 ID（自增主键） |
| user_id | INT | 用户 ID（外键） |
| token | VARCHAR(255) | Token（UUID） |
| expires_at | DATETIME | 过期时间 |
| created_at | DATETIME | 创建时间 |

#### 3. 新闻分类表 (news_category)

```sql
CREATE TABLE news_category (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    sort_order INT DEFAULT 0,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW()
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 分类 ID |
| name | VARCHAR(50) | 分类名称（唯一） |
| sort_order | INT | 排序序号 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### 4. 新闻表 (news)

```sql
CREATE TABLE news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    image VARCHAR(255) NOT NULL,
    author VARCHAR(50) NOT NULL,
    category_id INT NOT NULL,
    views INT DEFAULT 0,
    publish_time DATETIME NOT NULL,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    INDEX fk_news_category_idx (category_id),
    INDEX fk_news_created_at_idx (created_at),
    FOREIGN KEY (category_id) REFERENCES news_category(id)
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 新闻 ID |
| title | VARCHAR(255) | 新闻标题 |
| description | VARCHAR(500) | 新闻描述 |
| content | TEXT | 新闻正文（HTML） |
| image | VARCHAR(255) | 封面图片 URL |
| author | VARCHAR(50) | 作者 |
| category_id | INT | 分类 ID（外键） |
| views | INT | 浏览量 |
| publish_time | DATETIME | 发布时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### 5. 收藏表 (favorite)

```sql
CREATE TABLE favorite (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '收藏ID',
    user_id INT NOT NULL COMMENT '用户ID',
    news_id INT NOT NULL COMMENT '新闻ID',
    created_at DATETIME DEFAULT NOW() COMMENT '创建时间',
    UNIQUE KEY user_news_unique (user_id, news_id),
    INDEX fk_favorite_user_idx (user_id),
    INDEX fk_favorite_news_idx (news_id),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 收藏记录 ID（主键，自增） |
| user_id | INT | 用户 ID（外键） |
| news_id | INT | 新闻 ID（外键） |
| created_at | DATETIME | 收藏时间 |

**约束**: 同一用户不能重复收藏同一新闻（唯一约束 user_news_unique）

#### 6. 浏览历史表 (history)

```sql
CREATE TABLE history (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '历史ID',
    user_id INT NOT NULL COMMENT '用户ID',
    news_id INT NOT NULL COMMENT '新闻ID',
    view_time DATETIME NOT NULL COMMENT '浏览时间',
    INDEX fk_history_user_idx (user_id),
    INDEX fk_history_news_idx (news_id),
    INDEX idx_view_time (view_time),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 历史记录 ID（主键，自增） |
| user_id | INT | 用户 ID（外键） |
| news_id | INT | 新闻 ID（外键） |
| view_time | DATETIME | 浏览时间 |

---

## 系统架构

### 后端架构分层

```
┌─────────────────────────────────────┐
│         API Routes (routers/)       │  ← 路由层：定义 API 端点
├─────────────────────────────────────┤
│         CURD (curd/)                │  ← 业务逻辑层：数据库操作
├─────────────────────────────────────┤
│         Models (models/)            │  ← 数据模型层：ORM 映射
├─────────────────────────────────────┤
│         Schemas (schemas/)          │  ← 数据验证层：Pydantic 校验
├─────────────────────────────────────┤
│         Cache (cache/)              │  ← 缓存层：Redis 操作
├─────────────────────────────────────┤
│         Utils (utils/)              │  ← 工具层：认证、加密、响应
├─────────────────────────────────────┤
│         Config (config/)            │  ← 配置层：数据库、缓存、AI
└─────────────────────────────────────┘
```

### 请求处理流程

```
客户端请求
    ↓
CORS 中间件
    ↓
API 日志中间件（记录请求信息、SSE流式处理）
    ↓
路由匹配 (routers/)
    ↓
依赖注入 (认证、数据库会话)
    ↓
全局异常处理器
    ↓
业务逻辑处理 (curd/)
    ↓
缓存检查 (cache/) → 命中则返回
    ↓
数据库操作 (models/)
    ↓
数据序列化 (schemas/)
    ↓
统一响应封装 (utils/response.py)
    ↓
日志记录响应信息
    ↓
返回客户端
```

### 缓存策略

| 缓存类型 | 缓存键格式 | TTL | 说明 |
|----------|-----------|-----|------|
| 分类缓存 | `news:categories` | 600s | 新闻分类列表 |
| 列表缓存 | `news:list:{category_id}:{page}:{page_size}` | 600s | 新闻列表分页数据 |

### 认证流程

```
┌──────────┐     登录/注册      ┌──────────┐
│  客户端   │ ────────────────→ │  服务端   │
│          │ ←──────────────── │          │
│          │   返回 Token       │          │
└──────────┘                    └──────────┘
     ↓
┌──────────┐  携带 Token 请求   ┌──────────┐
│  客户端   │ ────────────────→ │  服务端   │
│          │   (Header)         │          │
│          │ ←──────────────── │          │
│          │   返回数据         │          │
└──────────┘                    └──────────┘
```

---

## 部署与运行

### 环境要求

| 项目 | 版本要求 |
|------|----------|
| Python | >=3.11 |
| MySQL | >=5.7 |
| Redis | >=6.0 |
| Node.js | >=16 (前端) |

### 后端部署

#### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

#### 2. 配置数据库

编辑 `TouTiaoApp/config/db_conf.py`:

```python
ASYNC_DATABASE_URL = "mysql+aiomysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4"
```

#### 3. 配置 Redis

编辑 `TouTiaoApp/config/cache_conf.py`:

```python
REDIS_URL = "redis://:密码@主机:端口/数据库编号"
```

#### 4. 启动服务

```bash
# 开发环境
uvicorn TouTiaoApp.main:app --reload --host 0.0.0.0 --port 8000

# 生产环境
uvicorn TouTiaoApp.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 前端部署

#### 1. 安装依赖

```bash
cd xwzx-news
npm install
```

#### 2. 配置 API 地址

编辑 `xwzx-news/src/config/api.js`:

```javascript
export const API_BASE_URL = 'http://127.0.0.1:8000';
```

#### 3. 启动开发服务器

```bash
npm run dev
```

#### 4. 生产构建

```bash
npm run build
```

构建产物在 `xwzx-news/dist` 目录，可部署到 Nginx 等 Web 服务器。

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/xwzx-news/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Docker 部署（可选）

#### Dockerfile（后端）

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

COPY TouTiaoApp ./toutiao_app

EXPOSE 8000

CMD ["uvicorn", "TouTiaoApp.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### docker-compose.yml

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: 123456
      MYSQL_DATABASE: news_app
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql+aiomysql://root:123456@mysql:3306/news_app
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - mysql
      - redis

  frontend:
    image: node:18-alpine
    working_dir: /app
    volumes:
      - ./xwzx-news:/app
    command: sh -c "npm install && npm run build"

volumes:
  mysql_data:
```

### 数据库初始化

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE news_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 运行迁移脚本（如果有）
python scripts/init_db.py
```

---

## 文档说明

本文档提供 Toutiao App 所有接口的详细说明，按功能模块分组，所有参数均使用表格格式展示。

---

## 1. 基础规范

### 1.1 服务协议

| 项目 | 说明 |
|------|------|
| 协议 | HTTP/HTTPS |
| 主机 | 127.0.0.1:8000（开发环境） |
| 基础路径 | /api |
| 字符编码 | UTF-8 |
| 数据格式 | JSON |
| 时间格式 | ISO 8601（YYYY-MM-DDTHH:mm:ss） |

### 1.2 统一响应结构

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | integer | 业务状态码（200成功，其他失败） |
| message | string | 响应消息 |
| data | object/array/null | 响应数据 |

### 1.3 HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未授权（Token无效或过期） |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 500 | 服务器内部错误 |

### 1.4 认证方式

- **认证类型**: Bearer Token
- **请求头**: `Authorization: Bearer <token>`
- **Token有效期**: 7天
- **获取方式**: 登录或注册接口

---

## 2. 用户模块 (Users)

**基础路径**: `/api/user`

### 接口列表

| 接口名称 | 方法 | 路径 | 说明 | 认证 |
|----------|------|------|------|------|
| 用户注册 | POST | `/register` | 创建新用户账号 | ❌ |
| 用户登录 | POST | `/login` | 用户登录获取Token | ❌ |
| 获取用户信息 | GET | `/info` | 获取当前用户详细信息 | ✅ |
| 更新用户信息 | PUT | `/update` | 更新用户个人资料（含头像Base64） | ✅ |
| 修改密码 | PUT | `/password` | 修改用户登录密码 | ✅ |

---

### 2.1 用户注册

**接口描述**: 创建新用户账号，密码会自动加密存储

**请求定义**:
```
POST /api/user/register
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| username | string | 是 | 长度3-50 | 用户名，全局唯一 |
| password | string | 是 | 长度≥6 | 密码，明文传输（建议HTTPS） |

**请求示例**:
```json
{
  "username": "testuser",
  "password": "123456"
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "username": "testuser",
    "token": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 409 | 409 | 用户名已存在 | 用户名已被注册 |
| 400 | 400 | 用户名长度不合法 | 用户名长度不符合要求 |
| 400 | 400 | 密码长度不合法 | 密码长度不符合要求 |
| 500 | 500 | 注册失败 | 数据库操作失败 |

**业务规则**:
- 用户名必须唯一
- 密码使用bcrypt加密存储
- 注册成功后自动生成Token

---

### 2.2 用户登录

**接口描述**: 用户登录获取Token

**请求定义**:
```
POST /api/user/login
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| username | string | 是 | 长度3-50 | 用户名 |
| password | string | 是 | - | 密码 |

**请求示例**:
```json
{
  "username": "testuser",
  "password": "123456"
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "username": "testuser",
    "token": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 用户名或密码错误 | 用户名不存在或密码错误 |
| 400 | 400 | 用户名长度不合法 | 用户名长度不符合要求 |
| 500 | 500 | 登录失败 | 服务器错误 |

**业务规则**:
- 登录成功后生成新Token（旧Token失效）
- Token有效期7天
- 密码验证使用bcrypt比对

---

### 2.3 获取用户信息

**接口描述**: 获取当前登录用户的详细信息

**请求定义**:
```
GET /api/user/info
Authorization: Bearer <token>
```

**请求参数**: 无

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "username": "testuser",
    "nickname": "测试用户",
    "avatar": "https://example.com/avatar.jpg",
    "bio": "个人简介",
    "gender": "male",
    "phone": "13800138000"
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效或已过期 |

---

### 2.4 更新用户信息

**接口描述**: 更新当前用户的个人资料

**请求定义**:
```
PUT /api/user/update
Authorization: Bearer <token>
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| nickname | string | 否 | 长度≤50 | 昵称 |
| bio | string | 否 | 长度≤500 | 个人简介 |
| avatar | string | 否 | 无限制 | 头像URL或Base64编码（支持长字符串） |
| gender | string | 否 | 长度≤10 | 性别（male/female/other） |
| phone | string | 否 | 长度≤11 | 手机号 |

**说明**: 
- 所有字段均为可选，只更新提供的字段
- `avatar` 字段支持 URL 或 Base64 编码的图片数据（无长度限制）
- Base64 格式示例: `data:image/jpeg;base64,/9j/4AAQSkZJRg...`

**请求示例**:
```json
{
  "nickname": "新昵称",
  "bio": "新的个人简介",
  "avatar": "https://example.com/new-avatar.jpg"
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "username": "testuser",
    "nickname": "新昵称",
    "avatar": "https://example.com/new-avatar.jpg",
    "bio": "新的个人简介",
    "gender": "female",
    "phone": "13900139000"
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |
| 404 | 404 | User not found | 用户不存在 |

---

### 2.5 修改密码

**接口描述**: 修改当前用户的登录密码

**请求定义**:
```
PUT /api/user/password
Authorization: Bearer <token>
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| oldPassword | string | 是 | - | 旧密码 |
| newPassword | string | 是 | 长度≥6 | 新密码 |

**请求示例**:
```json
{
  "oldPassword": "123456",
  "newPassword": "654321"
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": true
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |
| 401 | 401 | 旧密码错误 | 旧密码验证失败 |
| 500 | 500 | 修改密码失败 | 数据库更新失败 |

**业务规则**:
- 必须先验证旧密码正确性
- 新密码长度至少6位
- 密码修改成功后，建议重新登录获取新Token

---

## 3. 新闻模块 (News)

**基础路径**: `/api/news`

### 接口列表

| 接口名称 | 方法 | 路径 | 说明 | 认证 |
|----------|------|------|------|------|
| 获取分类列表 | GET | `/categories` | 获取新闻分类列表 | ❌ |
| 获取新闻列表 | GET | `/list` | 分页获取新闻列表 | ❌ |
| 获取新闻详情 | GET | `/detail` | 获取新闻详细信息 | ❌ |

---

### 3.1 获取新闻分类

**接口描述**: 获取新闻分类列表，支持缓存

**请求定义**:
```
GET /api/news/categories
```

**请求参数**:

| 参数名 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|--------|------|------|--------|------|------|
| skip | integer | 否 | 0 | ≥0 | 跳过数量（偏移量） |
| limit | integer | 否 | 10 | 1-100 | 返回数量 |

**请求示例**:
```
GET /api/news/categories?skip=0&limit=10
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "科技",
      "sort_order": 1
    },
    {
      "id": 2,
      "name": "体育",
      "sort_order": 2
    },
    {
      "id": 3,
      "name": "娱乐",
      "sort_order": 3
    }
  ]
}
```

**缓存策略**:
- **缓存键**: `news:categories`
- **TTL**: 600秒（10分钟）
- **更新策略**: 过期后自动从数据库重新加载

---

### 3.2 获取新闻列表

**接口描述**: 分页获取指定分类的新闻列表，支持缓存

**请求定义**:
```
GET /api/news/list
```

**请求参数**:

| 参数名 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|--------|------|------|--------|------|------|
| categoryId | integer | 是 | - | >0 | 分类ID |
| page | integer | 否 | 1 | ≥1 | 页码 |
| pageSize | integer | 是 | - | 1-100 | 每页数量 |

**请求示例**:
```
GET /api/news/list?categoryId=1&page=1&pageSize=10
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 100,
    "page": 1,
    "pageSize": 10,
    "list": [
      {
        "id": 1,
        "title": "AI技术最新突破",
        "description": "人工智能领域取得重大进展...",
        "image": "https://example.com/image.jpg",
        "author": "张三",
        "categoryId": 1,
        "views": 1000,
        "publishedTime": "2026-05-23T10:00:00"
      }
    ],
    "hasMore": true
  }
}
```

**缓存策略**:
- **缓存键**: `news:list:{category_id}:{page}:{page_size}`
- **TTL**: 600秒（10分钟）
- **示例**: `news:list:1:1:10`

---

### 3.3 获取新闻详情

**接口描述**: 获取新闻详细信息，自动增加浏览量，返回相关新闻

**请求定义**:
```
GET /api/news/detail
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| id | integer | 是 | >0 | 新闻ID |

**请求示例**:
```
GET /api/news/detail?id=1
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "title": "AI技术最新突破",
    "content": "<p>新闻正文内容...</p>",
    "image": "https://example.com/image.jpg",
    "author": "张三",
    "publishTime": "2026-05-23T10:00:00",
    "categoryId": 1,
    "views": 1001,
    "relatedNews": [
      {
        "id": 2,
        "title": "相关新闻标题",
        "description": "相关新闻描述",
        "image": "https://example.com/related.jpg",
        "author": "李四",
        "categoryId": 1,
        "views": 500,
        "publishedTime": "2026-05-22T10:00:00"
      }
    ]
  }
}
```

**业务规则**:
- 每次查看自动增加浏览量（views +1）
- 返回同一分类下的相关新闻（最多5条）
- 排除当前新闻本身
- 前端支持点击相关推荐跳转到对应新闻详情
- 从相关推荐返回时，自动返回到该新闻所属分类的首页

---

## 4. 收藏模块 (Favorite)

**基础路径**: `/api/favorite`

### 接口列表

| 接口名称 | 方法 | 路径 | 说明 | 认证 |
|----------|------|------|------|------|
| 添加收藏 | POST | `/add` | 收藏指定新闻 | ✅ |
| 取消收藏 | DELETE | `/remove` | 取消收藏指定新闻 | ✅ |
| 获取收藏列表 | GET | `/list` | 获取用户收藏列表 | ✅ |
| 检查收藏状态 | GET | `/check` | 检查是否已收藏某新闻 | ✅ |

---

### 4.1 添加收藏

**接口描述**: 收藏指定新闻

**请求定义**:
```
POST /api/favorite/add
Authorization: Bearer <token>
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| newsId | integer | 是 | >0 | 新闻ID |

**请求示例**:
```json
{
  "newsId": 1
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "userId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "newsId": 1,
    "createdAt": "2026-05-23T10:00:00"
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |
| 409 | 409 | 已收藏该新闻 | 重复收藏 |
| 404 | 404 | 新闻不存在 | 新闻ID不存在 |

**业务规则**:
- 同一用户不能重复收藏同一新闻
- 需要用户登录认证

---

### 4.2 取消收藏

**接口描述**: 取消收藏指定新闻

**请求定义**:
```
DELETE /api/favorite/remove
Authorization: Bearer <token>
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| newsId | integer | 是 | >0 | 新闻ID |

**请求示例**:
```json
{
  "newsId": 1
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": true
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |
| 404 | 404 | 收藏记录不存在 | 未收藏该新闻 |

---

### 4.3 获取收藏列表

**接口描述**: 获取当前用户的收藏列表

**请求定义**:
```
GET /api/favorite/list
Authorization: Bearer <token>
```

**请求参数**:

| 参数名 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|--------|------|------|--------|------|------|
| page | integer | 否 | 1 | ≥1 | 页码 |
| pageSize | integer | 是 | - | 1-100 | 每页数量 |

**请求示例**:
```
GET /api/favorite/list?page=1&pageSize=10
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 50,
    "page": 1,
    "pageSize": 10,
    "list": [
      {
        "id": 1,
        "newsId": 1,
        "newsTitle": "新闻标题",
        "newsDescription": "新闻描述",
        "newsImage": "https://example.com/image.jpg",
        "newsAuthor": "张三",
        "createdAt": "2026-05-23T10:00:00"
      }
    ],
    "hasMore": true
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |

---

### 4.4 检查收藏状态

**接口描述**: 检查当前用户是否已收藏某新闻

**请求定义**:
```
GET /api/favorite/check
Authorization: Bearer <token>
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| newsId | integer | 是 | >0 | 新闻ID |

**请求示例**:
```
GET /api/favorite/check?newsId=1
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "isFavorite": true,
    "favoriteId": 1
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |

---

## 5. 历史记录模块 (History)

**基础路径**: `/api/history`

### 接口列表

| 接口名称 | 方法 | 路径 | 说明 | 认证 |
|----------|------|------|------|------|
| 添加浏览记录 | POST | `/add` | 记录新闻浏览历史 | ✅ |
| 获取历史列表 | GET | `/list` | 获取用户浏览历史 | ✅ |
| 删除单条记录 | DELETE | `/delete/{history_id}` | 删除指定浏览记录 | ✅ |
| 清空历史记录 | DELETE | `/clear` | 清空所有浏览记录 | ✅ |

---

### 5.1 添加浏览记录

**接口描述**: 记录用户浏览新闻的历史

**请求定义**:
```
POST /api/history/add
Authorization: Bearer <token>
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| newsId | integer | 是 | >0 | 新闻ID |

**请求示例**:
```json
{
  "newsId": 1
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "userId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "newsId": 1,
    "createdAt": "2026-05-23T10:00:00"
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |
| 404 | 404 | 新闻不存在 | 新闻ID不存在 |

---

### 5.2 获取历史列表

**接口描述**: 获取用户的浏览历史记录

**请求定义**:
```
GET /api/history/list
Authorization: Bearer <token>
```

**请求参数**:

| 参数名 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|--------|------|------|--------|------|------|
| page | integer | 否 | 1 | ≥1 | 页码 |
| pageSize | integer | 是 | - | 1-100 | 每页数量 |

**请求示例**:
```
GET /api/history/list?page=1&pageSize=10
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 50,
    "page": 1,
    "pageSize": 10,
    "list": [
      {
        "id": 1,
        "newsId": 1,
        "newsTitle": "新闻标题",
        "newsDescription": "新闻描述",
        "newsImage": "https://example.com/image.jpg",
        "newsAuthor": "张三",
        "createdAt": "2026-05-23T10:00:00"
      }
    ],
    "hasMore": true
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |

---

### 5.3 删除单条历史记录

**接口描述**: 删除指定的浏览记录

**请求定义**:
```
DELETE /api/history/delete/{history_id}
Authorization: Bearer <token>
```

**请求参数**:

| 参数名 | 类型 | 必填 | 约束 | 说明 |
|--------|------|------|------|------|
| history_id | integer | 是 | >0 | 历史记录ID（路径参数） |

**请求示例**:
```
DELETE /api/history/delete/1
```

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": true
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |
| 404 | 404 | 记录不存在 | 历史记录ID不存在 |

---

### 5.4 清空历史记录

**接口描述**: 清空当前用户的所有浏览记录

**请求定义**:
```
DELETE /api/history/clear
Authorization: Bearer <token>
```

**请求参数**: 无

**响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "deletedCount": 50
  }
}
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 401 | 401 | 无效令牌或已过期 | Token无效 |

---

## 6. AI 问答模块 (AI Chat)

**基础路径**: `/api/ai`

### 接口列表

| 接口名称 | 方法 | 路径 | 说明 | 认证 |
|----------|------|------|------|------|
| AI智能问答 | POST | `/chat` | 与AI进行对话 | ❌ |

---

### 6.1 AI智能问答

**接口描述**: 支持流式和非流式两种响应方式，可与AI进行对话

**请求定义**:
```
POST /api/ai/chat
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| message | string | 是 | - | 用户输入的消息 |
| history | array | 否 | [] | 对话历史记录 |
| stream | boolean | 否 | false | 是否流式响应（true=流式，false=非流式） |

**history参数结构**:

| 字段 | 类型 | 说明 |
|------|------|------|
| role | string | 角色（user/assistant） |
| content | string | 消息内容 |

**请求示例**:
```json
{
  "message": "你好",
  "history": [
    {"role": "user", "content": "之前的对话"},
    {"role": "assistant", "content": "之前的回复"}
  ],
  "stream": false
}
```

**响应示例（非流式）**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "reply": "你好！有什么我可以帮你的吗？",
    "usage": {
      "prompt_tokens": 10,
      "completion_tokens": 20,
      "total_tokens": 30
    }
  }
}
```

**响应示例（流式）**:
```
Content-Type: text/event-stream

data: {"id":"...","choices":[{"delta":{"content":"你好"}}]}
data: {"id":"...","choices":[{"delta":{"content":"！"}}]}
data: {"id":"...","choices":[{"delta":{"content":"有什么"}}]}
data: {"id":"...","choices":[{"delta":{"content":"我可以"}}]}
data: {"id":"...","choices":[{"delta":{"content":"帮你的"}}]}
data: {"id":"...","choices":[{"delta":{"content":"吗？"}}]}
data: [DONE]
```

**错误响应**:

| 状态码 | code | message | 说明 |
|--------|------|---------|------|
| 400 | 400 | 消息不能为空 | message参数为空 |
| 500 | 500 | AI服务调用失败 | 外部AI服务异常 |
| 504 | 504 | 请求超时 | AI服务响应超时 |

**业务规则**:
- 流式响应使用Server-Sent Events (SSE)
- 非流式响应使用标准JSON格式
- 建议携带history参数以保持对话上下文
- 单次对话最大token数限制由AI服务配置

---

## 附录

### A. 快速测试示例

#### 用户注册
```bash
curl -X POST http://127.0.0.1:8000/api/user/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"123456"}'
```

#### 用户登录
```bash
curl -X POST http://127.0.0.1:8000/api/user/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"123456"}'
```

#### 获取新闻分类
```bash
curl -X GET "http://127.0.0.1:8000/api/news/categories?skip=0&limit=10"
```

#### 获取新闻列表
```bash
curl -X GET "http://127.0.0.1:8000/api/news/list?categoryId=1&page=1&pageSize=10"
```

#### 获取新闻详情
```bash
curl -X GET "http://127.0.0.1:8000/api/news/detail?id=1"
```

#### 添加收藏（需要Token）
```bash
curl -X POST http://127.0.0.1:8000/api/favorite/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{"newsId":1}'
```

#### AI对话（流式）
```bash
curl -X POST http://127.0.0.1:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好","stream":true}'
```

---

**文档版本**: v2.2  
**最后更新**: 2026-05-23  
**维护者**: Toutiao App 开发团队

---

## 更新日志

### v2.2 (2026-05-23)
- ✅ 新增头像上传功能，支持 Base64 编码（无长度限制）
- ✅ 新增新闻详情相关推荐跳转功能，可点击进入相关新闻
- ✅ 优化返回按钮逻辑，从相关推荐返回时跳转到分类首页
- ✅ 修复 Vue Router 同路径导航不刷新问题，使用 watch 监听路由参数变化
- ✅ 前端 My.vue 页面头像动态绑定，实时显示用户上传的头像
- ✅ 后端 users.py schema 优化，avatar 字段移除 max_length 限制
- ✅ 数据库模型优化，avatar 字段使用 Text 类型支持长文本
- ✅ 完善项目结构文档，补充组件详细说明
- ✅ 添加 Pinia PersistedState 持久化插件到技术栈

### v2.1 (2026-05-23)
- ✅ 修正项目目录结构，统一使用 `TouTiaoApp` 目录名
- ✅ 更新数据库表结构，与实际模型保持一致（user/user_token/favorite/history）
- ✅ 修正用户ID字段类型为 INT（原为 VARCHAR(36) UUID）
- ✅ 更新AI问答接口响应格式，匹配实际返回结构
- ✅ 添加 log_utils.py 工具文件说明
- ✅ 启用SQLAlchemy SQL日志输出
- ✅ 优化SSE流式响应日志记录
