from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.schemas.dify import OrderDifyOutput


FIELD_LABELS: dict[str, str] = {
    "customer_name": "客户",
    "phone": "联系电话",
    "product_name": "商品",
    "quantity": "数量",
    "size": "尺寸",
    "flavor": "口味",
    "message_on_cake": "蛋糕留言",
    "pickup_time": "取货时间",
    "delivery_time": "配送时间",
    "delivery_address": "配送地址",
    "budget_max": "预算",
    "notes": "备注",
}

FIELD_QUESTIONS: dict[str, str] = {
    "product_name": "想要订什么商品？",
    "quantity": "需要几份？",
    "size": "需要什么尺寸？",
    "flavor": "想要什么口味？",
    "pickup_time": "计划什么时候取货？",
    "delivery_time": "希望什么时候送达？",
    "delivery_address": "送到什么地址？",
    "phone": "方便留一个联系电话吗？",
    "budget_max": "预算大概是多少？",
    "notes": "还有其他忌口或备注吗？",
}

SCENARIO_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "cake": (
        "customer_name",
        "phone",
        "product_name",
        "quantity",
        "size",
        "flavor",
        "pickup_time",
    ),
    "flower": (
        "product_name",
        "quantity",
        "pickup_time",
        "delivery_address",
    ),
    "repair": (
        "product_name",
        "notes",
        "pickup_time",
        "phone",
    ),
}

CONFIRMATION_FIELD_ORDER = (
    "customer_name",
    "phone",
    "product_name",
    "quantity",
    "size",
    "flavor",
    "message_on_cake",
    "pickup_time",
    "delivery_time",
    "delivery_address",
    "budget_max",
    "notes",
)


def build_order_requirements(analysis: OrderDifyOutput) -> dict[str, Any]:
    requirements: dict[str, Any] = {}
    for field in FIELD_LABELS:
        value = getattr(analysis, field, None)
        if value is not None and value != "":
            requirements[field] = value
    if analysis.extra_requirements:
        requirements.update(analysis.extra_requirements)
    if (
        analysis.scenario == "cake"
        and requirements.get("product_name") not in (None, "", "蛋糕")
        and str(requirements["product_name"]).endswith("蛋糕")
    ):
        requirements["product_name"] = "蛋糕"
    return requirements


def missing_order_fields(
    requirements: dict[str, Any],
    scenario: str = "cake",
) -> list[str]:
    required_fields = SCENARIO_REQUIRED_FIELDS.get(
        scenario,
        SCENARIO_REQUIRED_FIELDS["cake"],
    )
    return [
        field
        for field in required_fields
        if not _field_is_present(field, requirements)
    ]


def format_order_follow_up(
    missing_fields: list[str],
    requirements: dict[str, Any],
    scenario: str = "cake",
) -> str:
    if not missing_fields:
        return format_order_confirmation(requirements, scenario)

    lines: list[str] = []
    if requirements:
        lines.append("当前已记录：")
        for field in CONFIRMATION_FIELD_ORDER:
            value = requirements.get(field)
            if value is not None and value != "":
                lines.append(f"- {_label(field)}：{value}")
        lines.append("")

    lines.append("还需要确认：")
    for field in missing_fields:
        question = FIELD_QUESTIONS.get(field, f"请补充{_label(field)}。")
        lines.append(f"- {question}")
    return "\n".join(lines)


def format_order_confirmation(
    requirements: dict[str, Any],
    scenario: str = "cake",
) -> str:
    lines = ["请确认订单信息："]
    lines.extend(_format_requirement_lines(requirements))
    lines.append("")
    if not requirements.get("message_on_cake") or not requirements.get("notes"):
        lines.append(
            "是否需要补充蛋糕留言或备注？有的话请补充，"
            "没有可以回复“没有”。"
        )
        lines.append("")
    lines.append("回复“确认下单”后，我会把订单提交给店主。")
    return "\n".join(lines)


def format_order_summary(
    requirements: dict[str, Any],
    scenario: str = "cake",
) -> str:
    lines = _format_requirement_lines(requirements)
    if not lines:
        return "订单信息为空。"
    return "\n".join(lines)


def _format_requirement_lines(requirements: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for field in CONFIRMATION_FIELD_ORDER:
        value = requirements.get(field)
        if value is not None and value != "":
            lines.append(f"- {_label(field)}：{value}")

    for field, value in requirements.items():
        if field not in FIELD_LABELS and value is not None and value != "":
            lines.append(f"- {_label(field)}：{value}")
    return lines


def _field_is_present(field: str, requirements: dict[str, Any]) -> bool:
    if field == "pickup_time":
        return bool(
            requirements.get("pickup_time")
            or requirements.get("delivery_time")
        )
    value = requirements.get(field)
    return value is not None and value != ""


def _label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def annotate_relative_times(
    requirements: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(
        ZoneInfo(get_settings().app_timezone)
    )
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo(get_settings().app_timezone))

    for field in ("pickup_time", "delivery_time"):
        value = requirements.get(field)
        if isinstance(value, str) and value:
            requirements[field] = annotate_relative_time(value, current)
    return requirements


def annotate_relative_time(value: str, now: datetime) -> str:
    cleaned = value.strip()
    if cleaned.startswith("(") and ")" in cleaned:
        return cleaned

    day_offsets = {
        "今天": 0,
        "明天": 1,
        "后天": 2,
        "大后天": 3,
    }
    for prefix, offset in day_offsets.items():
        if cleaned.startswith(prefix):
            target = now + timedelta(days=offset)
            return f"({target.month}.{target.day}){cleaned}"

    weekday_match = cleaned[:1] == "周" and cleaned[1:2] in {
        "一",
        "二",
        "三",
        "四",
        "五",
        "六",
        "日",
        "天",
    }
    if weekday_match:
        weekday_text = cleaned[1]
        weekday_index = {
            "一": 0,
            "二": 1,
            "三": 2,
            "四": 3,
            "五": 4,
            "六": 5,
            "日": 6,
            "天": 6,
        }[weekday_text]
        delta = (weekday_index - now.weekday()) % 7
        if delta == 0:
            delta = 7
        target = now + timedelta(days=delta)
        return f"({target.month}.{target.day}){cleaned}"

    return cleaned
