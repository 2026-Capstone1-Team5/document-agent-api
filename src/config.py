from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DOCUMENT_AGENT_API_",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/document_agent_api"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
