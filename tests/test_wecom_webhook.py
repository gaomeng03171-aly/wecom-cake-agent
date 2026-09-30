import json

import httpx

from app.clients.wecom import WebhookWeComSender
from app.models import OutboxMessage


def _outbox_message() -> OutboxMessage:
    return OutboxMessage(
        id=1,
        group_id="group-001",
        content="聚餐提醒",
        status="pending",
    )


def test_webhook_sender_posts_text_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == httpx.URL("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test")
        assert json.loads(request.content) == {
            "msgtype": "text",
            "text": {"content": "聚餐提醒"},
        }
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    sender = WebhookWeComSender(
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
        transport=httpx.MockTransport(handler),
    )

    result = sender.send(_outbox_message())

    assert result.success is True
    assert result.provider_message_id is None


def test_webhook_sender_returns_wecom_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errcode": 93000, "errmsg": "invalid webhook key"},
        )

    sender = WebhookWeComSender(
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
        transport=httpx.MockTransport(handler),
    )

    result = sender.send(_outbox_message())

    assert result.success is False
    assert result.error == "invalid webhook key"
