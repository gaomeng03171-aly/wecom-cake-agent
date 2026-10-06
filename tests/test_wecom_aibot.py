import asyncio
import time

from sqlalchemy import select

from app.clients.wecom import SendResult
from app.config import Settings
from app.db import get_session_factory
from app.models import OutboxMessage, OutboxStatus
from app.services.outbox import enqueue_reply
from app.services.wecom_aibot import (
    WeComAiBotFrameNormalizer,
    WeComAiBotLongConnectionWorker,
)


def _group_frame(
    *,
    msg_id: str = "aibot-msg-001",
    content: str = "周六晚上一起吃饭吗",
) -> dict:
    return {
        "cmd": "aibot_msg_callback",
        "headers": {"req_id": f"req-{msg_id}"},
        "body": {
            "msgid": msg_id,
            "chatid": "real-group-001",
            "chattype": "group",
            "chat_name": "周末聚餐群",
            "from": {"userid": "user-001", "name": "张三"},
            "msgtype": "text",
            "text": {"content": content},
            "create_time": 1791031103,
        },
    }


def test_aibot_normalizer_maps_group_text_frame() -> None:
    payload = WeComAiBotFrameNormalizer().normalize(_group_frame())

    assert payload is not None
    assert payload.msg_id == "aibot-msg-001"
    assert payload.group_id == "real-group-001"
    assert payload.group_name == "周末聚餐群"
    assert payload.sender_id == "user-001"
    assert payload.content == "周六晚上一起吃饭吗"


def test_aibot_normalizer_maps_single_chat_to_direct_group() -> None:
    frame = _group_frame(msg_id="aibot-single-001", content="你好")
    frame["body"].pop("chatid")
    frame["body"]["chattype"] = "single"

    payload = WeComAiBotFrameNormalizer().normalize(frame)

    assert payload is not None
    assert payload.group_id == "direct-user-001"


def test_aibot_normalizer_combines_mixed_text_items() -> None:
    frame = _group_frame(msg_id="aibot-mixed-001")
    frame["body"]["msgtype"] = "mixed"
    frame["body"].pop("text")
    frame["body"]["mixed"] = {
        "items": [
            {"type": "text", "text": {"content": "周六"}},
            {"type": "image", "image": {"media_id": "media-001"}},
            {"type": "text", "text": {"content": "晚上"}},
        ]
    }

    payload = WeComAiBotFrameNormalizer().normalize(frame)

    assert payload is not None
    assert payload.msg_type == "mixed"
    assert payload.content == "周六晚上"


def test_aibot_worker_requires_mention_when_bot_is_configured() -> None:
    settings = Settings(
        wecom_aibot_id="BOT_ID",
        wecom_aibot_name="聚餐助手",
        wecom_aibot_require_mention=True,
    )
    worker = WeComAiBotLongConnectionWorker(
        ws_client=FakeAiBotWsClient(),
        settings=settings,
    )
    frame = _group_frame()

    assert worker._should_process(frame) is False

    frame["body"]["mentioned_users"] = ["BOT_ID"]
    assert worker._should_process(frame) is True


def test_aibot_worker_allows_single_chat_without_mention() -> None:
    settings = Settings(
        wecom_aibot_id="BOT_ID",
        wecom_aibot_name="订单助手",
        wecom_aibot_require_mention=True,
    )
    worker = WeComAiBotLongConnectionWorker(
        ws_client=FakeAiBotWsClient(),
        settings=settings,
    )
    frame = _group_frame()
    frame["body"]["chattype"] = "single"
    frame["body"].pop("chatid", None)

    assert worker._should_process(frame) is True


class FakeAiBotWsClient:
    def __init__(self) -> None:
        self.handlers = {}
        self.connected = False
        self.disconnected = False
        self.replies = []
        self.sent_messages = []

    def on(self, event: str, handler) -> None:
        self.handlers[event] = handler

    async def connect(self) -> None:
        self.connected = True
        authenticated = self.handlers.get("authenticated")
        if authenticated is not None:
            authenticated()

    async def disconnect(self) -> None:
        self.disconnected = True

    async def reply(self, frame: dict, body: dict) -> dict:
        self.replies.append((frame, body))
        return {"errcode": 0, "errmsg": "ok", "body": {"msgid": "reply-001"}}

    async def send_message(self, chatid: str, body: dict) -> dict:
        self.sent_messages.append((chatid, body))
        return {"errcode": 0, "errmsg": "ok", "body": {"msgid": "send-001"}}


def test_aibot_worker_processes_group_frame_and_replies(client) -> None:
    ws_client = FakeAiBotWsClient()
    worker = WeComAiBotLongConnectionWorker(ws_client=ws_client)

    async def run() -> None:
        await worker.start()
        await ws_client.handlers["message.text"](_group_frame())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if len(ws_client.replies) == 1:
                break
            await asyncio.sleep(0.02)
        await worker.stop()

    asyncio.run(run())

    assert ws_client.connected is True
    assert ws_client.disconnected is True
    assert len(ws_client.replies) == 1
    assert ws_client.replies[0][1]["msgtype"] == "markdown"


def test_aibot_worker_does_not_reply_twice_for_duplicate_frame(client) -> None:
    ws_client = FakeAiBotWsClient()
    worker = WeComAiBotLongConnectionWorker(ws_client=ws_client)
    frame = _group_frame(msg_id="aibot-duplicate-001")

    async def run() -> None:
        await worker.start()
        await ws_client.handlers["message.text"](frame)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if len(ws_client.replies) == 1:
                break
            await asyncio.sleep(0.02)
        await ws_client.handlers["message.text"](frame)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if len(ws_client.replies) == 1:
                break
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.1)
        await worker.stop()

    asyncio.run(run())

    assert len(ws_client.replies) == 1


def test_aibot_worker_returns_generated_proposal_list(client) -> None:
    ws_client = FakeAiBotWsClient()
    worker = WeComAiBotLongConnectionWorker(ws_client=ws_client)

    async def run() -> None:
        await worker.start()
        await ws_client.handlers["message.text"](
            _group_frame(msg_id="aibot-create-001", content="周六晚上一起吃饭吗")
        )
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if len(ws_client.replies) == 1:
                break
            await asyncio.sleep(0.02)
        await ws_client.handlers["message.text"](
            _group_frame(msg_id="aibot-proposals-001", content="生成方案")
        )
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if len(ws_client.replies) == 2:
                break
            await asyncio.sleep(0.02)
        await worker.stop()

    asyncio.run(run())

    assert len(ws_client.replies) == 2
    reply = ws_client.replies[1][1]["markdown"]["content"]
    assert "1. " in reply
    assert "我选1" in reply


def test_aibot_worker_routes_order_scenario_and_notifies_owner(client) -> None:
    settings = Settings(
        agent_scenario="order",
        wecom_aibot_id="BOT_ID",
        wecom_aibot_name="订单助手",
        wecom_aibot_require_mention=False,
        wecom_owner_user_id="owner-001",
        order_notification_channel="active",
    )
    ws_client = FakeAiBotWsClient()
    worker = WeComAiBotLongConnectionWorker(
        ws_client=ws_client,
        settings=settings,
    )

    async def run() -> None:
        await worker.start()
        await ws_client.handlers["message.text"](
            _group_frame(
                msg_id="order-aibot-001",
                content="我叫张三，电话13800138000，我想订一个8寸草莓蛋糕",
            )
        )
        await _wait_for(lambda: len(ws_client.replies) == 1)
        await ws_client.handlers["message.text"](
            _group_frame(
                msg_id="order-aibot-002",
                content="明天下午三点取",
            )
        )
        await _wait_for(lambda: len(ws_client.replies) == 2)
        await ws_client.handlers["message.text"](
            _group_frame(
                msg_id="order-aibot-003",
                content="确认下单",
            )
        )
        await _wait_for(
            lambda: len(ws_client.replies) == 3
            and len(ws_client.sent_messages) == 1
        )
        await worker.stop()

    asyncio.run(run())

    assert ws_client.sent_messages[0][0] == "owner-001"
    assert "新订单已确认" in ws_client.sent_messages[0][1]["markdown"]["content"]


def test_aibot_worker_retries_pending_active_outbox(client) -> None:
    with get_session_factory()() as db:
        outbox = enqueue_reply(
            db,
            group_id="direct-owner-001",
            content="新订单已确认：蛋糕订单",
            dispatch_channel="active",
        )
        outbox_id = outbox.id

    settings = Settings(
        wecom_aibot_id="BOT_ID",
        wecom_aibot_name="订单助手",
        wecom_aibot_require_mention=False,
        outbox_retry_poll_seconds=1,
    )
    ws_client = FakeAiBotWsClient()
    worker = WeComAiBotLongConnectionWorker(
        ws_client=ws_client,
        settings=settings,
    )

    async def run() -> None:
        await worker.start()
        await _wait_for(lambda: len(ws_client.sent_messages) == 1)
        await worker.stop()

    asyncio.run(run())

    assert ws_client.sent_messages[0][0] == "owner-001"
    with get_session_factory()() as db:
        message = db.scalar(
            select(OutboxMessage).where(OutboxMessage.id == outbox_id)
        )
        assert message is not None
        assert message.status == OutboxStatus.SENT.value


def test_aibot_worker_dispatches_app_channel_outbox(
    client,
    monkeypatch,
) -> None:
    from app.services import wecom_aibot

    class FakeAppSender:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def send(self, message):
            return SendResult(
                success=True,
                provider_message_id="app-msg-001",
            )

    monkeypatch.setattr(wecom_aibot, "AppWeComSender", FakeAppSender)

    with get_session_factory()() as db:
        outbox = enqueue_reply(
            db,
            group_id="direct-owner-001",
            content="新订单已确认：蛋糕订单",
            dispatch_channel="app",
        )
        outbox_id = outbox.id

    settings = Settings(
        wecom_corp_id="corp-001",
        wecom_app_secret="secret-001",
        wecom_agent_id="100001",
        outbox_retry_poll_seconds=1,
    )
    worker = WeComAiBotLongConnectionWorker(
        ws_client=FakeAiBotWsClient(),
        settings=settings,
    )

    async def run() -> None:
        await worker.start()
        await _wait_for(lambda: _outbox_status(outbox_id) == "sent")
        await worker.stop()

    asyncio.run(run())


def _outbox_status(outbox_id: int) -> str | None:
    with get_session_factory()() as db:
        message = db.scalar(
            select(OutboxMessage).where(OutboxMessage.id == outbox_id)
        )
        return message.status if message is not None else None


async def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("Timed out waiting for AiBot worker condition")
