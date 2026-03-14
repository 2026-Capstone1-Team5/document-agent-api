import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/document_agent_api"
DEFAULT_CORS_ALLOW_ORIGINS = ["https://document-agent-web.vercel.app"]
DEFAULT_AUTH_SECRET_KEY = "dev-only-change-this-key"
DEFAULT_AUTH_ACCESS_TOKEN_TTL_SECONDS = 1800


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
    auth_secret_key: str = DEFAULT_AUTH_SECRET_KEY
    auth_access_token_ttl_seconds: int = DEFAULT_AUTH_ACCESS_TOKEN_TTL_SECONDS

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
