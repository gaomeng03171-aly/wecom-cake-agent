from abc import ABC, abstractmethod
from dataclasses import dataclass

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


def get_wecom_sender() -> WeComSender:
    settings = get_settings()
    if settings.wecom_sender_mode == "mock":
        return MockWeComSender()

    raise RuntimeError("Real WeCom sender is not implemented yet.")
