from typing import Any

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
