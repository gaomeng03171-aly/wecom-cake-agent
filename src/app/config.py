from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "wecom-dinner-agent"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    admin_api_key: str = ""
    database_url: str = "sqlite:///./dev.db"
    auto_create_tables: bool = True

    dify_client_mode: str = "mock"
    dify_api_base: str = ""
    dify_api_key: str = ""
    dify_user: str = "wecom-dinner-agent"
    dify_timeout_seconds: float = 30.0

    wecom_sender_mode: str = "mock"
    wecom_webhook_url: str = ""
    wecom_sender_timeout_seconds: float = 10.0
    wecom_corp_id: str = ""
    wecom_agent_id: str = ""
    wecom_app_secret: str = ""

    reminder_scheduler_enabled: bool = True
    reminder_poll_seconds: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
