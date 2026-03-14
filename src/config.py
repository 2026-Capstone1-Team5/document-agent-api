from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/document_agent_api"
DEFAULT_CORS_ALLOW_ORIGINS = ["https://document-agent-web.vercel.app"]


def normalize_database_url(database_url: str) -> str:
    lowered = database_url.lower()
    if lowered.startswith("postgres://"):
        return f"postgresql+psycopg://{database_url[len('postgres://') :]}"
    if lowered.startswith("postgresql://"):
        return f"postgresql+psycopg://{database_url[len('postgresql://') :]}"
    return database_url


def normalize_cors_allow_origins(origins: str | list[str]) -> list[str]:
    if isinstance(origins, str):
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
    cors_allow_origins: list[str] = Field(default_factory=lambda: DEFAULT_CORS_ALLOW_ORIGINS.copy())

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def validate_cors_allow_origins(cls, value: str | list[str]) -> list[str]:
        return normalize_cors_allow_origins(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
