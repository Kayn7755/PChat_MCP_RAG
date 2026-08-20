# Modular RAG MCP Server

A modular RAG system exposed as an MCP Server, with a Streamlit management dashboard.

## Quick start (local)

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install ".[dev]"
cp .env.example .env   # set OPENAI_API_KEY
python scripts/start_dashboard.py
```

## Docker (cloud VM)

```bash
cp .env.example .env   # set OPENAI_API_KEY
docker compose up -d --build
# Dashboard: http://<host>:8501
```

## MCP (local stdio)

Configure your MCP client to run `python -m src.mcp_server.server` from this repo.
