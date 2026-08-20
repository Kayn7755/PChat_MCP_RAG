# PChatMind Agent image: FastAPI + built UI + Modular RAG (for MCP stdio child).
# Build from monorepo root:
#   docker compose build agent

# ----- UI -----
FROM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY PChatMind-python-agent/ui/package.json PChatMind-python-agent/ui/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY PChatMind-python-agent/ui/ ./
RUN npm run build

# ----- runtime -----
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    JCHATMIND_HOST=0.0.0.0 \
    JCHATMIND_PORT=8080 \
    JCHATMIND_RAG_PROVIDER=mcp \
    JCHATMIND_MCP_RAG_SERVER_CWD=/app/modular-rag \
    JCHATMIND_MCP_DEFAULT_COLLECTION=default \
    JCHATMIND_DOCUMENT_STORAGE_BASE_PATH=/app/data/documents

WORKDIR /app

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
      sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    fi

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Agent Python deps
COPY PChatMind-python-agent/requirements.txt /tmp/agent-requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/agent-requirements.txt

# Modular RAG (MCP Server + hybrid search); Agent spawns: python -m src.mcp_server.server
COPY MODULAR-RAG-MCP-SERVER-main /app/modular-rag
RUN pip install /app/modular-rag "openai>=1.0" \
    && mkdir -p /app/modular-rag/data /app/modular-rag/logs /app/data/documents

# Agent source
COPY PChatMind-python-agent/jchatmind_agent /app/jchatmind_agent
COPY PChatMind-python-agent/jchatmind_app /app/jchatmind_app
COPY --from=ui /ui/dist /app/ui/dist

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/docs || exit 1

CMD ["python", "-m", "jchatmind_app"]
