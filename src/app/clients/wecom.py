from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

import httpx

from app.config import get_settings
from app.models import OutboxMessage

_token_cache: dict[tuple[str, str], tuple[str, datetime]] = {}
_token_lock = Lock()


@dataclass(frozen=True)
class SendResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class WeComSender(ABC):
    @abstractmethod
    def send(self, message: OutboxMessage) -> SendResult:
        raise NotImplementedError


class MockWeComSender(WeComSender):
    def send(self, message: OutboxMessage) -> SendResult:
        return SendResult(
            success=True,
            provider_message_id=f"mock-{message.id}",
        )


class WebhookWeComSender(WeComSender):
    def __init__(
        self,
        webhook_url: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def send(self, message: OutboxMessage) -> SendResult:
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    self._webhook_url,
                    json={
                        "msgtype": "text",
                        "text": {"content": message.content},
                    },
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return SendResult(
                success=False,
                error=f"WeCom webhook request failed: {exc}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return SendResult(
                success=False,
                error=f"WeCom webhook returned invalid JSON: {exc}",
            )

        error_code = payload.get("errcode")
        if error_code != 0:
            return SendResult(
                success=False,
                error=str(
                    payload.get("errmsg")
                    or f"WeCom webhook error code: {error_code}"
                ),
            )

        return SendResult(success=True)


class AppWeComSender(WeComSender):
    def __init__(
        self,
        corp_id: str,
        app_secret: str,
        agent_id: str,
        api_base: str = "https://qyapi.weixin.qq.com",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._corp_id = corp_id
        self._app_secret = app_secret
        self._agent_id = int(agent_id)
        self._api_base = api_base.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def send(self, message: OutboxMessage) -> SendResult:
        try:
            access_token = self.get_access_token()
        except RuntimeError as exc:
            return SendResult(success=False, error=str(exc))

        try:
            with httpx.Client(
                base_url=self._api_base,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                if message.group_id.startswith("direct-"):
                    response = client.post(
                        "cgi-bin/message/send",
                        params={"access_token": access_token},
                        json={
                            "touser": message.group_id.removeprefix("direct-"),
                            "msgtype": "text",
                            "agentid": self._agent_id,
                            "text": {"content": message.content},
                            "safe": 0,
                        },
                    )
                else:
                    response = client.post(
                        "cgi-bin/appchat/send",
                        params={"access_token": access_token},
                        json={
                            "chatid": message.group_id,
                            "msgtype": "text",
                            "text": {"content": message.content},
                        },
                    )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return SendResult(
                success=False,
                error=f"WeCom app message request failed: {exc}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return SendResult(
                success=False,
                error=f"WeCom app message returned invalid JSON: {exc}",
            )

        error_code = payload.get("errcode")
        if error_code != 0:
            return SendResult(
                success=False,
                error=str(
                    payload.get("errmsg")
                    or f"WeCom app message error code: {error_code}"
                ),
            )

        provider_message_id = payload.get("msgid")
        return SendResult(
            success=True,
            provider_message_id=(
                str(provider_message_id) if provider_message_id else None
            ),
        )

    def get_access_token(self) -> str:
        cache_key = (self._corp_id, self._app_secret)
        now = datetime.now(timezone.utc)

        with _token_lock:
            cached = _token_cache.get(cache_key)
            if cached is not None and cached[1] > now + timedelta(seconds=60):
                return cached[0]

            try:
                with httpx.Client(
                    base_url=self._api_base,
                    timeout=self._timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = client.get(
                        "cgi-bin/gettoken",
                        params={
                            "corpid": self._corp_id,
                            "corpsecret": self._app_secret,
                        },
                    )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RuntimeError(f"failed to get WeCom access token: {exc}") from exc

            if payload.get("errcode") != 0:
                raise RuntimeError(
                    str(payload.get("errmsg") or "failed to get WeCom access token")
                )

            access_token = str(payload["access_token"])
            expires_in = int(payload.get("expires_in", 7200))
            expires_at = now + timedelta(seconds=max(expires_in - 60, 60))
            _token_cache[cache_key] = (access_token, expires_at)
            return access_token


def get_wecom_sender() -> WeComSender:
    settings = get_settings()
    if settings.wecom_sender_mode == "mock":
        return MockWeComSender()
    if settings.wecom_sender_mode == "webhook":
        if not settings.wecom_webhook_url:
            raise RuntimeError("WECOM_WEBHOOK_URL is required")
        return WebhookWeComSender(
            webhook_url=settings.wecom_webhook_url,
            timeout_seconds=settings.wecom_sender_timeout_seconds,
        )
    if settings.wecom_sender_mode in {"app", "real"}:
        if (
            not settings.wecom_corp_id
            or not settings.wecom_app_secret
            or not settings.wecom_agent_id
        ):
            raise RuntimeError(
                "WECOM_CORP_ID, WECOM_APP_SECRET and WECOM_AGENT_ID are required"
            )
        return AppWeComSender(
            corp_id=settings.wecom_corp_id,
            app_secret=settings.wecom_app_secret,
            agent_id=settings.wecom_agent_id,
            api_base=settings.wecom_api_base,
            timeout_seconds=settings.wecom_sender_timeout_seconds,
        )

    raise RuntimeError(f"Unsupported WeCom sender mode: {settings.wecom_sender_mode}")
