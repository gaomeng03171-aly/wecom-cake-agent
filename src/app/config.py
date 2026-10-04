from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "wecom-cake-agent"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    agent_scenario: str = "order"
    admin_api_key: str = ""
    database_url: str = "sqlite:///./dev.db"
    auto_create_tables: bool = True

    dify_client_mode: str = "mock"
    dify_api_base: str = ""
    dify_api_key: str = ""
    dify_user: str = "wecom-cake-agent"
    dify_timeout_seconds: float = 30.0
    order_dify_mode: str = "auto"
    dify_order_api_base: str = ""
    dify_order_api_key: str = ""
    dify_order_user: str = "wecom-order-agent"
    dify_order_timeout_seconds: float = 30.0

    wecom_sender_mode: str = "mock"
    wecom_webhook_url: str = ""
    wecom_api_base: str = "https://qyapi.weixin.qq.com"
    wecom_sender_timeout_seconds: float = 10.0
    wecom_corp_id: str = ""
    wecom_agent_id: str = ""
    wecom_app_secret: str = ""
    wecom_callback_token: str = ""
    wecom_encoding_aes_key: str = ""
    wecom_callback_max_age_seconds: int = 300

    wecom_aibot_id: str = ""
    wecom_aibot_secret: str = ""
    wecom_aibot_ws_url: str = ""
    wecom_aibot_name: str = ""
    wecom_aibot_require_mention: bool = True
    wecom_owner_user_id: str = ""

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
