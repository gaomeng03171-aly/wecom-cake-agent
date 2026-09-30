from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.models import OutboxMessage


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


def get_wecom_sender() -> WeComSender:
    settings = get_settings()
    if settings.wecom_sender_mode == "mock":
        return MockWeComSender()
    if settings.wecom_sender_mode in {"webhook", "real"}:
        if not settings.wecom_webhook_url:
            raise RuntimeError("WECOM_WEBHOOK_URL is required")
        return WebhookWeComSender(
            webhook_url=settings.wecom_webhook_url,
            timeout_seconds=settings.wecom_sender_timeout_seconds,
        )

    raise RuntimeError(f"Unsupported WeCom sender mode: {settings.wecom_sender_mode}")
