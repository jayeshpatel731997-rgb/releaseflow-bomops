from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ReleaseFlow"
    database_url: str = "sqlite:///./releaseflow.db"
    extraction_mode: str = "fixture"
    max_upload_mb: int = 10
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
