from app.config import Settings
from app.db import get_engine
from app.schemas.activity import IntegrationStatusOut


def get_integration_status(settings: Settings) -> IntegrationStatusOut:
    sender_missing: list[str] = []
    sender_ready = True

    if settings.wecom_sender_mode == "webhook":
        if not settings.wecom_webhook_url:
            sender_missing.append("WECOM_WEBHOOK_URL")
    elif settings.wecom_sender_mode in {"app", "real"}:
        if not settings.wecom_corp_id:
            sender_missing.append("WECOM_CORP_ID")
        if not settings.wecom_agent_id:
            sender_missing.append("WECOM_AGENT_ID")
        if not settings.wecom_app_secret:
            sender_missing.append("WECOM_APP_SECRET")
    elif settings.wecom_sender_mode != "mock":
        sender_missing.append("WECOM_SENDER_MODE")

    callback_missing: list[str] = []
    if not settings.wecom_corp_id:
        callback_missing.append("WECOM_CORP_ID")
    if not settings.wecom_callback_token:
        callback_missing.append("WECOM_CALLBACK_TOKEN")
    if not settings.wecom_encoding_aes_key:
        callback_missing.append("WECOM_ENCODING_AES_KEY")

    dify_missing: list[str] = []
    if settings.dify_client_mode in {"real", "http"}:
        if not settings.dify_api_base:
            dify_missing.append("DIFY_API_BASE")
        if not settings.dify_api_key:
            dify_missing.append("DIFY_API_KEY")

    sender_ready = not sender_missing

    return IntegrationStatusOut(
        wecom_sender_mode=settings.wecom_sender_mode,
        wecom_sender_ready=sender_ready,
        missing_wecom_sender_config=sender_missing,
        wecom_callback_ready=not callback_missing,
        missing_wecom_callback_config=callback_missing,
        wecom_callback_url="/wecom/callback",
        dify_client_mode=settings.dify_client_mode,
        dify_ready=not dify_missing,
        missing_dify_config=dify_missing,
        database_dialect=get_engine().dialect.name,
    )
