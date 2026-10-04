import asyncio
import time

from app.config import Settings
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


class FakeAiBotWsClient:
    def __init__(self) -> None:
        self.handlers = {}
        self.connected = False
        self.disconnected = False
        self.replies = []

    def on(self, event: str, handler) -> None:
        self.handlers[event] = handler

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    async def reply(self, frame: dict, body: dict) -> dict:
        self.replies.append((frame, body))
        return {"errcode": 0, "errmsg": "ok", "body": {"msgid": "reply-001"}}


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

    messages = client.get(
        "/admin/messages",
        params={"group_id": "real-group-001"},
    ).json()
    assert len(messages) == 1
    assert messages[0]["wecom_msg_id"] == "aibot-msg-001"


def test_aibot_worker_does_not_reply_twice_for_duplicate_frame(client) -> None:
    ws_client = FakeAiBotWsClient()
    worker = WeComAiBotLongConnectionWorker(ws_client=ws_client)
    frame = _group_frame(msg_id="aibot-duplicate-001")

    async def run() -> None:
        await worker.start()
        await ws_client.handlers["message.text"](frame)
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
