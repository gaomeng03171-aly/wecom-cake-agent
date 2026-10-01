from datetime import datetime, timezone
from xml.etree import ElementTree

from app.schemas.wecom import WeComMessageIn


class WeComCallbackMessageError(ValueError):
    pass


def validate_callback_timestamp(
    timestamp: str,
    max_age_seconds: int,
    now_timestamp: int | None = None,
) -> None:
    try:
        callback_timestamp = int(timestamp)
    except ValueError as exc:
        raise WeComCallbackMessageError("invalid callback timestamp") from exc

    current_timestamp = (
        now_timestamp
        if now_timestamp is not None
        else int(datetime.now(timezone.utc).timestamp())
    )
    if abs(current_timestamp - callback_timestamp) > max_age_seconds:
        raise WeComCallbackMessageError("callback timestamp is outside the allowed window")


def parse_callback_message(xml_text: str) -> WeComMessageIn:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise WeComCallbackMessageError("invalid callback XML") from exc

    def value(name: str, default: str = "") -> str:
        return root.findtext(name, default=default)

    msg_id = value("MsgId") or value("MsgID")
    sender_id = value("FromUserName")
    if not msg_id or not sender_id:
        raise WeComCallbackMessageError("callback message is missing MsgId or FromUserName")

    create_time_text = value("CreateTime")
    create_time = None
    if create_time_text.isdigit():
        create_time = datetime.fromtimestamp(
            int(create_time_text),
            tz=timezone.utc,
        )

    return WeComMessageIn(
        msg_id=msg_id,
        group_id=value("ChatId") or f"direct-{sender_id}",
        group_name=value("ChatName"),
        sender_id=sender_id,
        sender_name=value("FromUserName"),
        msg_type=value("MsgType", default="text"),
        content=value("Content"),
        create_time=create_time,
        raw_payload={"xml": xml_text},
    )
