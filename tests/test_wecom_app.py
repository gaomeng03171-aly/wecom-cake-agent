import json

import httpx

from app.clients.wecom import AppWeComSender
from app.models import OutboxMessage


def _outbox_message(group_id: str) -> OutboxMessage:
    return OutboxMessage(
        id=10,
        group_id=group_id,
        content="聚餐提醒",
        status="pending",
    )


def test_app_sender_posts_to_group_chat() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/cgi-bin/gettoken":
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "access_token": "group-token",
                    "expires_in": 7200,
                },
            )

        assert request.url.path == "/cgi-bin/appchat/send"
        assert request.url.params["access_token"] == "group-token"
        assert json.loads(request.content) == {
            "chatid": "group-chat-001",
            "msgtype": "text",
            "text": {"content": "聚餐提醒"},
        }
        return httpx.Response(
            200,
            json={"errcode": 0, "errmsg": "ok", "msgid": "msg-001"},
        )

    sender = AppWeComSender(
        corp_id="corp-group",
        app_secret="secret-group",
        agent_id="100001",
        transport=httpx.MockTransport(handler),
    )

    result = sender.send(_outbox_message("group-chat-001"))

    assert result.success is True
    assert result.provider_message_id == "msg-001"


def test_app_sender_posts_direct_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/cgi-bin/gettoken":
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "access_token": "direct-token",
                    "expires_in": 7200,
                },
            )

        assert request.url.path == "/cgi-bin/message/send"
        assert request.url.params["access_token"] == "direct-token"
        assert json.loads(request.content) == {
            "touser": "user-001",
            "msgtype": "text",
            "agentid": 100001,
            "text": {"content": "聚餐提醒"},
            "safe": 0,
        }
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    sender = AppWeComSender(
        corp_id="corp-direct",
        app_secret="secret-direct",
        agent_id="100001",
        transport=httpx.MockTransport(handler),
    )

    result = sender.send(_outbox_message("direct-user-001"))

    assert result.success is True


def test_app_sender_returns_token_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errcode": 40001, "errmsg": "invalid app secret"},
        )

    sender = AppWeComSender(
        corp_id="corp-error",
        app_secret="secret-error",
        agent_id="100001",
        transport=httpx.MockTransport(handler),
    )

    result = sender.send(_outbox_message("group-chat-error"))

    assert result.success is False
    assert result.error == "invalid app secret"
