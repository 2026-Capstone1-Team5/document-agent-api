import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/document_agent_api"
DEFAULT_CORS_ALLOW_ORIGINS = ["https://document-agent-web.vercel.app"]
DEFAULT_AUTH_ACCESS_TOKEN_TTL_SECONDS = 1800
DEFAULT_STORAGE_BACKEND = "local"
DEFAULT_STORAGE_LOCAL_ROOT = "data/storage"
DEFAULT_STORAGE_R2_REGION = "auto"
DEFAULT_QUEUE_BACKEND = "memory"
DEFAULT_PARSE_JOB_QUEUE_NAME = "document-agent-api:parse-jobs"
DEFAULT_WORKER_POLL_TIMEOUT_SECONDS = 5
DEFAULT_DOCUMENT_AI_TIMEOUT_SECONDS = 300
DEFAULT_WORKER_TEMP_ROOT = "/tmp/document-agent-api-worker"
DEFAULT_PARSER_BACKEND = "pdftotext"
DEFAULT_PDFTOTEXT_COMMAND = "pdftotext"


def normalize_database_url(database_url: str) -> str:
    lowered = database_url.lower()
    if lowered.startswith("postgres://"):
        return f"postgresql+psycopg://{database_url[len('postgres://') :]}"
    if lowered.startswith("postgresql://"):
        return f"postgresql+psycopg://{database_url[len('postgresql://') :]}"
    return database_url


def normalize_cors_allow_origins(origins: str | list[str]) -> list[str]:
    if isinstance(origins, str):
        raw = origins.strip()
        parsed_json: list[str] | None = None
        if raw.startswith("["):
            try:
                json_value = json.loads(raw)
                if isinstance(json_value, list):
                    parsed_json = [str(item).strip() for item in json_value]
            except json.JSONDecodeError:
                parsed_json = None

        if parsed_json is not None:
            candidates = parsed_json
        else:
            candidates = [item.strip() for item in origins.split(",")]
    else:
        candidates = [item.strip() for item in origins]

    normalized: list[str] = []
    for origin in candidates:
        if not origin:
            continue
        normalized_origin = origin.rstrip("/")
        if normalized_origin and normalized_origin not in normalized:
            normalized.append(normalized_origin)
    return normalized


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    database_url: str = DEFAULT_DATABASE_URL
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: DEFAULT_CORS_ALLOW_ORIGINS.copy(),
    )
    auth_secret_key: str
    auth_access_token_ttl_seconds: int = DEFAULT_AUTH_ACCESS_TOKEN_TTL_SECONDS
    storage_backend: str = DEFAULT_STORAGE_BACKEND
    storage_local_root: str = DEFAULT_STORAGE_LOCAL_ROOT
    storage_bucket: str | None = None
    storage_r2_endpoint: str | None = None
    storage_r2_access_key_id: str | None = None
    storage_r2_secret_access_key: str | None = None
    storage_r2_region: str = DEFAULT_STORAGE_R2_REGION
    queue_backend: str = DEFAULT_QUEUE_BACKEND
    redis_url: str = "redis://127.0.0.1:6379/0"
    parse_job_queue_name: str = DEFAULT_PARSE_JOB_QUEUE_NAME
    worker_poll_timeout_seconds: int = DEFAULT_WORKER_POLL_TIMEOUT_SECONDS
    document_ai_timeout_seconds: int = DEFAULT_DOCUMENT_AI_TIMEOUT_SECONDS
    worker_temp_root: str = DEFAULT_WORKER_TEMP_ROOT
    parser_backend: str = DEFAULT_PARSER_BACKEND
    pdftotext_command: str = DEFAULT_PDFTOTEXT_COMMAND
    document_ai_command: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def validate_cors_allow_origins(cls, value: str | list[str]) -> list[str]:
        return normalize_cors_allow_origins(value)

    @field_validator("auth_secret_key")
    @classmethod
    def validate_auth_secret_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "auth_secret_key must not be empty"
            raise ValueError(msg)
        return normalized

    @field_validator("auth_access_token_ttl_seconds")
    @classmethod
    def validate_auth_access_token_ttl_seconds(cls, value: int) -> int:
        if value <= 0:
            msg = "auth_access_token_ttl_seconds must be greater than 0"
            raise ValueError(msg)
        return value

    @field_validator("storage_backend")
    @classmethod
    def validate_storage_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local", "r2"}:
            msg = "storage_backend must be one of: local, r2"
            raise ValueError(msg)
        return normalized

    @field_validator(
        "storage_bucket",
        "storage_r2_endpoint",
        "storage_r2_access_key_id",
        "storage_r2_secret_access_key",
        mode="before",
    )
    @classmethod
    def normalize_optional_storage_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("storage_r2_region")
    @classmethod
    def validate_storage_r2_region(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "storage_r2_region must not be empty"
            raise ValueError(msg)
        return normalized

    @field_validator("queue_backend")
    @classmethod
    def validate_queue_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"memory", "redis", "logging"}:
            msg = "queue_backend must be one of: memory, redis, logging"
            raise ValueError(msg)
        return normalized

    @field_validator("parse_job_queue_name")
    @classmethod
    def validate_non_empty_queue_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "queue settings must not be empty"
            raise ValueError(msg)
        return normalized

    @field_validator("redis_url")
    @classmethod
    def normalize_redis_url(cls, value: str) -> str:
        return value.strip()

    @field_validator("document_ai_command", mode="before")
    @classmethod
    def normalize_document_ai_command(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("parser_backend")
    @classmethod
    def validate_parser_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"pdftotext", "document_ai"}:
            msg = "parser_backend must be one of: pdftotext, document_ai"
            raise ValueError(msg)
        return normalized

    @field_validator("pdftotext_command")
    @classmethod
    def validate_pdftotext_command(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "pdftotext_command must not be empty"
            raise ValueError(msg)
        return normalized

    @field_validator("worker_poll_timeout_seconds", "document_ai_timeout_seconds")
    @classmethod
    def validate_positive_worker_timeout(cls, value: int) -> int:
        if value <= 0:
            msg = "worker timeouts must be greater than 0"
            raise ValueError(msg)
        return value

    @field_validator("worker_temp_root")
    @classmethod
    def validate_worker_temp_root(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "worker_temp_root must not be empty"
            raise ValueError(msg)
        return normalized

    @model_validator(mode="after")
    def validate_storage_requirements(self) -> "Settings":
        if self.storage_backend == "r2":
            missing: list[str] = []
            if not self.storage_bucket:
                missing.append("storage_bucket")
            if not self.storage_r2_endpoint:
                missing.append("storage_r2_endpoint")
            if not self.storage_r2_access_key_id:
                missing.append("storage_r2_access_key_id")
            if not self.storage_r2_secret_access_key:
                missing.append("storage_r2_secret_access_key")

            if missing:
                joined = ", ".join(missing)
                msg = f"Missing required R2 settings: {joined}"
                raise ValueError(msg)

        if self.queue_backend == "redis" and not self.redis_url:
            msg = "redis_url is required when queue_backend=redis"
            raise ValueError(msg)

        if self.parser_backend == "document_ai" and not self.document_ai_command:
            msg = "document_ai_command is required when parser_backend=document_ai"
            raise ValueError(msg)

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
