from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Wehbi Nuts API"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = (
        "postgresql+psycopg://wehbi_nuts:wehbi_nuts@localhost:5432/wehbi_nuts"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
