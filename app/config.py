from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StockFlow"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://stockflow:stockflow@db:5432/stockflow"
    secret_key: str = "replace-this-with-a-long-random-secret"
    access_token_expire_minutes: int = 30
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str = "StockFlow Administrator"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
