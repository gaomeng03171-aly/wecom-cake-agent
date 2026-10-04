import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.clients.wecom import SendResult
from app.config import Settings, get_settings
from app.db import get_session_factory
from app.schemas.wecom import WeComMessageIn
from app.services.outbox import apply_send_result
from app.services.processing import process_inbound_message

logger = logging.getLogger(__name__)


class WeComAiBotFrameNormalizer:
    def normalize(self, frame: dict[str, Any]) -> WeComMessageIn | None:
        body = frame.get("body")
        if not isinstance(body, dict):
            return None

        msg_type = self._message_type(body)
        if msg_type not in {"text", "mixed"}:
            return None

        content = self._content(body, msg_type)
        if not content:
            return None

        sender = body.get("from")
        sender = sender if isinstance(sender, dict) else {}
        sender_id = str(
            sender.get("userid")
            or sender.get("user_id")
            or body.get("userid")
            or body.get("user_id")
            or ""
        )
        if not sender_id:
            return None

        sender_name = str(
            sender.get("name")
            or sender.get("user_name")
            or body.get("sender_name")
            or sender_id
        )
        chat_id = body.get("chatid") or body.get("chat_id")
        chat_type = self._chat_type(
            body.get("chattype") or body.get("chat_type")
        )
        if chat_type == "single" or not chat_id:
            group_id = f"direct-{sender_id}"
        else:
            group_id = str(chat_id)

        group_name = body.get("chat_name") or body.get("chatname") or ""
        chat = body.get("chat")
        if isinstance(chat, dict) and not group_name:
            group_name = chat.get("name") or chat.get("chat_name") or ""

        msg_id = body.get("msgid") or body.get("msg_id")
        if not msg_id:
            headers = frame.get("headers")
            if isinstance(headers, dict):
                msg_id = headers.get("req_id")
        if not msg_id:
            msg_id = "aibot-" + _stable_hash(body)

        return WeComMessageIn(
            msg_id=str(msg_id),
            group_id=group_id,
            group_name=str(group_name or ""),
            sender_id=sender_id,
            sender_name=sender_name,
            msg_type=msg_type,
            content=content,
            create_time=self._create_time(body),
            raw_payload=frame,
        )

    @staticmethod
    def _message_type(body: dict[str, Any]) -> str:
        value = body.get("msgtype")
        if value:
            return str(value)
        if isinstance(body.get("text"), dict) or body.get("text") is not None:
            return "text"
        if isinstance(body.get("mixed"), dict):
            return "mixed"
        return ""

    @staticmethod
    def _content(body: dict[str, Any], msg_type: str) -> str:
        if msg_type == "text":
            text = body.get("text")
            if isinstance(text, dict):
                return str(text.get("content") or "")
            return str(text or "")

        mixed = body.get("mixed")
        if not isinstance(mixed, dict):
            return ""
        items = mixed.get("items")
        if not isinstance(items, list):
            return ""
        parts: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, dict) and text.get("content") is not None:
                parts.append(str(text["content"]))
        return "".join(parts)

    @staticmethod
    def _chat_type(value: Any) -> str:
        if value is None:
            return ""
        normalized = str(value).lower()
        if normalized in {"1", "single", "direct"}:
            return "single"
        if normalized in {"2", "group"}:
            return "group"
        return normalized

    @staticmethod
    def _create_time(body: dict[str, Any]) -> datetime | None:
        value = body.get("create_time") or body.get("send_time")
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)


class WeComAiBotLongConnectionWorker:
    def __init__(
        self,
        *,
        ws_client: Any,
        session_factory: sessionmaker[Session] | None = None,
        normalizer: WeComAiBotFrameNormalizer | None = None,
    ) -> None:
        self.ws_client = ws_client
        self.session_factory = session_factory or get_session_factory()
        self.normalizer = normalizer or WeComAiBotFrameNormalizer()
        self._tasks: set[asyncio.Task[Any]] = set()

    async def start(self) -> None:
        for event_name in ("message.text", "message.mixed"):
            self.ws_client.on(event_name, self._handle_frame)
        await self.ws_client.connect()

    async def stop(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.ws_client.disconnect()

    async def _handle_frame(self, frame: dict[str, Any]) -> None:
        task = asyncio.create_task(self._process_frame(frame))
        self._tasks.add(task)
        task.add_done_callback(self._handle_task_done)

    def _handle_task_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("WeCom AiBot frame processing failed")

    async def _process_frame(self, frame: dict[str, Any]) -> None:
        payload = self.normalizer.normalize(frame)
        if payload is None:
            return

        pending = await asyncio.to_thread(self._process_message, payload)
        if pending is None:
            return
        outbox_id, content = pending

        try:
            raw_response = await self.ws_client.reply(
                frame,
                {
                    "msgtype": "markdown",
                    "markdown": {"content": content},
                },
            )
            result = _send_result(raw_response)
        except Exception as exc:
            result = SendResult(success=False, error=str(exc))

        await asyncio.to_thread(
            self._record_send_result,
            outbox_id,
            result,
        )

    def _process_message(
        self,
        payload: WeComMessageIn,
    ) -> tuple[int, str] | None:
        with self.session_factory() as db:
            response = process_inbound_message(db, payload, dispatch=False)
            if response.duplicate or response.outbox is None:
                return None
            return response.outbox.id, response.outbox.content

    def _record_send_result(self, outbox_id: int, result: SendResult) -> None:
        with self.session_factory() as db:
            apply_send_result(db, outbox_id, result)


def build_wecom_aibot_ws_client(settings: Settings | None = None) -> Any:
    active_settings = settings or get_settings()
    missing: list[str] = []
    if not active_settings.wecom_aibot_id:
        missing.append("WECOM_AIBOT_ID")
    if not active_settings.wecom_aibot_secret:
        missing.append("WECOM_AIBOT_SECRET")
    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} are required for WeCom AiBot long connection"
        )

    try:
        from wecom_aibot_sdk import WSClient
    except ImportError as exc:
        raise RuntimeError(
            "wecom-aibot-sdk is required for WeCom AiBot long connection"
        ) from exc

    return WSClient(
        active_settings.wecom_aibot_id,
        active_settings.wecom_aibot_secret,
        ws_url=active_settings.wecom_aibot_ws_url,
        reconnect_interval=1000,
        max_reconnect_attempts=-1,
        heartbeat_interval=30000,
        request_timeout=int(active_settings.wecom_sender_timeout_seconds * 1000),
    )


def _send_result(raw_response: Any) -> SendResult:
    if not isinstance(raw_response, dict):
        return SendResult(success=True)
    error_code = raw_response.get("errcode")
    if error_code not in {None, 0}:
        return SendResult(
            success=False,
            error=str(raw_response.get("errmsg") or f"errcode={error_code}"),
        )
    body = raw_response.get("body")
    if isinstance(body, dict):
        provider_message_id = body.get("msgid") or body.get("external_msgid")
    else:
        provider_message_id = raw_response.get("msgid")
    return SendResult(
        success=True,
        provider_message_id=(
            str(provider_message_id) if provider_message_id else None
        ),
    )


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
