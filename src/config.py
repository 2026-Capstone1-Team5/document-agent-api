from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/document_agent_api"


def normalize_database_url(database_url: str) -> str:
    lowered = database_url.lower()
    if lowered.startswith("postgres://"):
        return f"postgresql+psycopg://{database_url[len('postgres://') :]}"
    if lowered.startswith("postgresql://"):
        return f"postgresql+psycopg://{database_url[len('postgresql://') :]}"
    return database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    database_url: str = DEFAULT_DATABASE_URL

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
