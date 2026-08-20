# Modular RAG MCP Server — Dashboard image
# Builds a container that serves the Streamlit management UI.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# System libs used by chromadb / markitdown PDF path
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
# hatchling needs README.md (see pyproject.toml readme = "README.md")
COPY pyproject.toml README.md ./
COPY src ./src
COPY main.py ./
COPY config ./config
COPY scripts ./scripts

RUN pip install --upgrade pip \
    && pip install . "openai>=1.0"

# Persist knowledge base + logs outside the container when volumes are mounted
RUN mkdir -p /app/data /app/logs

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8501/_stcore/health || exit 1

# Bind 0.0.0.0 so the port is reachable from outside the container
CMD ["python", "-m", "streamlit", "run", \
     "src/observability/dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0"]
