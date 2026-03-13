# document-agent-api

`document-agent-api` is the FastAPI service layer for the Document AI project.

It is responsible for:
- document upload
- parsing execution
- result retrieval
- download and deletion APIs

This repository serves the Web app and can be consumed by a separate MCP repository. It does not implement local OCR or VLM parser internals.

## Stack

- Python package manager: `uv`
- Web framework: `FastAPI`
- ORM target: `SQLAlchemy 2.0`
- Schema layer: `Pydantic`
- Deployment target: Docker container
## Run

Install dependencies:

```bash
uv sync
```

Start the development server:

```bash
uv run fastapi dev src/main.py
```

Start without the FastAPI dev watcher:

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/healthz
```

## Project Layout

```text
document-agent-api/
  src/
    __init__.py
    main.py
  pyproject.toml
  uv.lock
```
