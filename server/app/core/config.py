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

    # Digitizer upload settings (Milestone 3). Paths are relative to the
    # server/ project root unless an absolute path is given.
    digitizer_upload_dir: str = "uploads/digitizer"
    digitizer_max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB per image
    digitizer_max_images_per_job: int = 20
    digitizer_max_image_dimension: int = 8000  # pixels, width or height

    # AI vision digitizer (Milestone 4). See
    # app/services/ai/openrouter_vision_digitizer.py for the full rationale.
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemini-2.5-flash-lite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
