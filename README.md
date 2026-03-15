# document-agent-api

`document-agent-api` is the FastAPI service layer for the Document AI project.

It is responsible for:
- document upload
- parsing execution
- result retrieval
- download and deletion APIs
- object storage persistence for source/result payloads

This repository serves the Web app and can be consumed by a separate MCP repository. It does not implement local OCR or VLM parser internals.

## Stack

- Python package manager: `uv`
- Web framework: `FastAPI`
- ORM target: `SQLAlchemy 2.0`
- Database target: `PostgreSQL`
- Schema layer: `Pydantic`
- Deployment target: Docker container

## Run

Create a local env file first:

```bash
cp .env.example .env
```

Start PostgreSQL with Docker Compose:

```bash
docker compose up -d
```

Install dependencies:

```bash
uv sync
```

Set the database URL:

```bash
export DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/document_agent_api'
```

On Railway, use `DATABASE_URL`.
`postgres://...` and `postgresql://...` are automatically normalized for SQLAlchemy `psycopg`.

Set allowed CORS origins:

```bash
export CORS_ALLOW_ORIGINS='https://document-agent-web.vercel.app'
```

You can provide multiple origins with a comma-separated string.

Set required auth token configuration:

```bash
export AUTH_SECRET_KEY='replace-with-random-secret'
export AUTH_ACCESS_TOKEN_TTL_SECONDS=1800
```

Set object storage configuration:

```bash
# local development backend (default)
export STORAGE_BACKEND='local'
export STORAGE_LOCAL_ROOT='data/storage'

# Cloudflare R2 backend
export STORAGE_BACKEND='r2'
export STORAGE_BUCKET='your-r2-bucket'
export STORAGE_R2_ENDPOINT='https://<accountid>.r2.cloudflarestorage.com'
export STORAGE_R2_ACCESS_KEY_ID='...'
export STORAGE_R2_SECRET_ACCESS_KEY='...'
export STORAGE_R2_REGION='auto'
```

Apply database migrations:

```bash
uv run alembic upgrade head
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

Auth examples:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"password123!"}'

curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"password123!"}'
```

API key examples:

```bash
ACCESS_TOKEN='paste-jwt-access-token'

curl -X POST http://127.0.0.1:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Claude Desktop"}'

curl http://127.0.0.1:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"

curl http://127.0.0.1:8000/api/v1/documents \
  -H 'X-API-Key: paste-issued-api-key'

curl http://127.0.0.1:8000/api/v1/documents \
  -H 'Authorization: Bearer paste-issued-api-key'
```

## Quality Checks

```bash
uv run ruff check src tests
uv run pyright
uv run pytest
```

If you want to run the DB-backed test suite against the Compose database:

```bash
export DOCUMENT_AGENT_API_TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/document_agent_api_test'
uv run pytest
```

## Project Layout

```text
document-agent-api/
  docker/
    postgres/
      init/
  docker-compose.yml
  migrations/
    versions/
  src/
    config.py
    database.py
    main.py
    documents/
      router.py
      schemas.py
      service.py
      dependencies.py
      models.py
  tests/
    documents/
  .env.example
  pyproject.toml
  alembic.ini
  uv.lock
```
