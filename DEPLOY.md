# 云服务器部署说明（Docker Compose + GitHub Actions）

## 组成

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| postgres | pchat-postgres | 内网 5432 | pgvector，首次用 `init_db.sql` 建表 |
| agent | pchat-agent | 8080 | FastAPI + UI；内部 stdio 拉起 Modular MCP |
| rag-dashboard | pchat-rag-dashboard | 8501 | 知识库入库 / 管理（与 Agent 共享 `modular_data`） |

## 首次上机

```bash
sudo mkdir -p /opt/pchat_mcp_rag && sudo chown $USER:$USER /opt/pchat_mcp_rag
git clone https://github.com/Kayn7755/PChat_MCP_RAG.git /opt/pchat_mcp_rag
cd /opt/pchat_mcp_rag
cp .env.example .env
nano .env   # 至少改 POSTGRES_PASSWORD、OPENAI_API_KEY、各 LLM Key

docker compose up -d --build
docker compose ps
```

访问：

- Agent UI / API：`http://<服务器IP>:8080`
- RAG Dashboard：`http://<服务器IP>:8501`（先在这里往 `default` collection 灌文档）

## 本地验证 Compose（可选）

在仓库根目录：

```bash
cp .env.example .env
# 编辑 .env
docker compose up -d --build
```

## GitHub Actions CI/CD

1. 仓库 → Settings → Secrets and variables → Actions，添加：

| Secret | 说明 |
|--------|------|
| `SSH_HOST` | 服务器 IP / 域名 |
| `SSH_USER` | SSH 用户 |
| `SSH_KEY` | 私钥全文 |
| `SSH_PORT` | 可选，默认 22 |
| `DEPLOY_DIR` | 可选，默认 `/opt/pchat_mcp_rag` |

2. 服务器已完成「首次上机」，且 `authorized_keys` 已放公钥  
3. 之后每次 `push` 到 `main`：Actions SSH → `git reset --hard origin/main` → `docker compose up -d --build`

## 本仓库新增的文件

- `docker-compose.yml` — 三服务编排  
- `PChatMind-python-agent/Dockerfile` — Agent 镜像（含 UI 构建 + Modular 源码）  
- `.env.example` — 环境变量模板  
- `.dockerignore` — 减小 build context  
- `.github/workflows/deploy.yml` — 自动部署  

## 注意

- `.env` 只放服务器，不要提交  
- Agent 与 Dashboard **共用** volume `modular_data`，否则一边入库一边检索不到  
- `POSTGRES_PASSWORD` 变更后需同步改 `.env`；已有 volume 时改密码不会自动更新库内密码  
- 生产建议前面加 Nginx/Caddy 做 HTTPS，并关闭直接暴露 5432  
