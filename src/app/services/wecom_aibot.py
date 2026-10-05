import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.clients.wecom import SendResult
from app.config import Settings, get_settings
from app.db import get_session_factory
from app.schemas.wecom import WeComMessageIn
from app.services.outbox import apply_send_result, list_due_active_outbox
from app.services.order_flow import process_order_message
from app.services.processing import process_inbound_message

logger = logging.getLogger(__name__)


@dataclass
class AiBotDispatchPlan:
    customer_outbox_id: int
    customer_content: str
    owner_outbox_id: int | None = None
    owner_target: str | None = None
    owner_content: str | None = None


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
        settings: Settings | None = None,
    ) -> None:
        self.ws_client = ws_client
        self.session_factory = session_factory or get_session_factory()
        self.normalizer = normalizer or WeComAiBotFrameNormalizer()
        self.settings = settings or get_settings()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._retry_task: asyncio.Task[Any] | None = None
        self._authenticated = asyncio.Event()

    async def start(self) -> None:
        for event_name in ("message.text", "message.mixed"):
            self.ws_client.on(event_name, self._handle_frame)
        self.ws_client.on("authenticated", self._mark_authenticated)
        await self.ws_client.connect()
        try:
            await asyncio.wait_for(self._authenticated.wait(), timeout=10)
        except TimeoutError:
            logger.warning(
                "AiBot authentication event was not received; "
                "starting retry loop anyway"
            )
        self._authenticated.clear()
        self._retry_task = asyncio.create_task(
            self._dispatch_pending_active_outboxes_forever()
        )

    def _mark_authenticated(self) -> None:
        self._authenticated.set()

    async def stop(self) -> None:
        if self._retry_task is not None:
            self._retry_task.cancel()
            await asyncio.gather(self._retry_task, return_exceptions=True)
            self._retry_task = None
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
        if not self._should_process(frame):
            return
        payload = self.normalizer.normalize(frame)
        if payload is None:
            return

        plan = await asyncio.to_thread(self._process_message, payload)
        if plan is None:
            return

        try:
            raw_response = await self.ws_client.reply(
                frame,
                {
                    "msgtype": "markdown",
                    "markdown": {"content": plan.customer_content},
                },
            )
            result = _send_result(raw_response)
        except Exception as exc:
            result = SendResult(success=False, error=str(exc))

        await asyncio.to_thread(
            self._record_send_result,
            plan.customer_outbox_id,
            result,
        )

        if (
            plan.owner_outbox_id is not None
            and plan.owner_target
            and plan.owner_content
            and getattr(self.ws_client, "send_message", None) is not None
        ):
            try:
                raw_response = await self.ws_client.send_message(
                    plan.owner_target,
                    {
                        "msgtype": "markdown",
                        "markdown": {"content": plan.owner_content},
                    },
                )
                result = _send_result(raw_response)
            except Exception as exc:
                result = SendResult(success=False, error=str(exc))

            await asyncio.to_thread(
                self._record_send_result,
                plan.owner_outbox_id,
                result,
            )

    async def _dispatch_pending_active_outboxes_forever(self) -> None:
        while True:
            try:
                await self._dispatch_pending_active_outboxes_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to dispatch pending active outbox messages")
            await asyncio.sleep(max(self.settings.outbox_retry_poll_seconds, 1))

    async def _dispatch_pending_active_outboxes_once(self) -> int:
        if getattr(self.ws_client, "send_message", None) is None:
            return 0

        pending = await asyncio.to_thread(self._load_due_active_outbox)
        sent_count = 0
        for outbox_id, target, content in pending:
            try:
                raw_response = await self.ws_client.send_message(
                    target,
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
            if result.success:
                sent_count += 1
        return sent_count

    def _load_due_active_outbox(self) -> list[tuple[int, str, str]]:
        with self.session_factory() as db:
            messages = list_due_active_outbox(db)
            return [
                (
                    message.id,
                    _active_target(message.group_id),
                    message.content,
                )
                for message in messages
            ]

    def _process_message(
        self,
        payload: WeComMessageIn,
    ) -> AiBotDispatchPlan | None:
        with self.session_factory() as db:
            if self.settings.agent_scenario == "order":
                result = process_order_message(
                    db,
                    payload,
                    settings=self.settings,
                    commit=True,
                )
                if result.duplicate or result.customer_outbox is None:
                    return None
                owner_target = None
                owner_outbox_id = None
                owner_content = None
                if result.owner_notification is not None:
                    owner_outbox_id = result.owner_notification.id
                    owner_content = result.owner_notification.content
                    owner_target = result.owner_notification.group_id
                    if owner_target.startswith("direct-"):
                        owner_target = owner_target.removeprefix("direct-")
                return AiBotDispatchPlan(
                    customer_outbox_id=result.customer_outbox.id,
                    customer_content=result.customer_outbox.content,
                    owner_outbox_id=owner_outbox_id,
                    owner_target=owner_target,
                    owner_content=owner_content,
                )

            response = process_inbound_message(db, payload, dispatch=False)
            if response.duplicate or response.outbox is None:
                return None
            return AiBotDispatchPlan(
                customer_outbox_id=response.outbox.id,
                customer_content=response.outbox.content,
            )

    def _record_send_result(self, outbox_id: int, result: SendResult) -> None:
        with self.session_factory() as db:
            apply_send_result(db, outbox_id, result)

    def _should_process(self, frame: dict[str, Any]) -> bool:
        if not self.settings.wecom_aibot_require_mention:
            return True

        bot_id = self.settings.wecom_aibot_id
        bot_name = self.settings.wecom_aibot_name
        if not bot_id and not bot_name:
            return True

        body = frame.get("body")
        if not isinstance(body, dict):
            return False

        mentioned = _mention_values(body.get("mentioned_users"))
        mentioned.update(_mention_values(body.get("mentions")))
        if bot_id and bot_id in mentioned:
            return True
        if bot_name and bot_name in mentioned:
            return True

        content = _frame_text(body)
        return bool(bot_name and f"@{bot_name}" in content)


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


def _mention_values(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    result: set[str] = set()
    for item in value:
        if isinstance(item, str):
            result.add(item)
        elif isinstance(item, dict):
            for key in ("userid", "user_id", "id", "name"):
                if item.get(key) is not None:
                    result.add(str(item[key]))
    return result


def _frame_text(body: dict[str, Any]) -> str:
    text = body.get("text")
    if isinstance(text, dict) and text.get("content") is not None:
        return str(text["content"])
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
        text_item = item.get("text")
        if isinstance(text_item, dict) and text_item.get("content") is not None:
            parts.append(str(text_item["content"]))
    return "".join(parts)


def _active_target(group_id: str) -> str:
    if group_id.startswith("direct-"):
        return group_id.removeprefix("direct-")
    return group_id
