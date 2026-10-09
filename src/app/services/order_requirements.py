import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
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

EXTRA_FIELD_LABELS: dict[str, str] = {
    "pieces_per_box": "规格",
    "candles": "蜡烛数量",
    "candle_count": "蜡烛数量",
    "cake_topper": "蛋糕插牌",
    "topper": "蛋糕插牌",
    "card_message": "贺卡留言",
    "greeting_card": "贺卡留言",
    "color": "颜色",
    "theme": "主题",
    "shape": "形状",
    "eggless": "是否无蛋",
    "sugar_free": "是否无糖",
    "allergies": "过敏信息",
}

EXTRA_FIELD_ALIASES: dict[str, str] = {
    "candles": "蜡烛数量",
    "candle_count": "蜡烛数量",
    "cake_topper": "蛋糕插牌",
    "topper": "蛋糕插牌",
    "card_message": "贺卡留言",
    "greeting_card": "贺卡留言",
    "eggless": "是否无蛋",
    "sugar_free": "是否无糖",
    "allergies": "过敏信息",
}

IGNORED_EXTRA_REQUIREMENT_KEYS = {
    "request_type",
}

NONSENSE_PRODUCT_KEYWORDS = (
    "混凝土",
    "水泥",
    "钢筋",
    "砖头",
    "玻璃",
    "塑料",
    "木头",
    "泥巴",
    "垃圾",
    "毒药",
    "化学品",
    "金属",
    "石头",
)

NONSENSE_DELIVERY_KEYWORDS = (
    "月球",
    "火星",
    "太空",
    "外太空",
    "宇宙",
    "银河",
    "太阳",
    "星际",
    "星球",
)

MENU_BYPASS_KEYWORDS = (
    "确认报价",
    "确认下单",
    "报价可以",
    "价格可以",
    "可以接受",
    "不接受",
    "取消订单",
    "取消",
    "退订",
    "不订了",
    "不要了",
    "不买了",
    "恢复订单",
    "恢复",
    "修改订单",
    "修改",
    "改备注",
    "改规格",
    "改商品",
    "改尺寸",
    "太贵",
    "好贵",
    "便宜",
    "优惠",
    "折扣",
    "降价",
    "做好",
    "制作进度",
    "定金",
)

MENU_INTRODUCTION_TEXT = """**巧克力系列**

- 黑森林蛋糕｜樱桃酒渍黑樱桃，黑巧碎与鲜奶油层层叠加
- 醇厚巧克力蛋糕｜比利时 70% 黑巧，三重巧克力口感，苦甜平衡

**茶香系列**

- 抹茶冰淇淋蛋糕｜宇治抹茶配蜜红豆，冰凉绵密，茶韵清香
- 伯爵茶奶油蛋糕｜锡兰伯爵茶香，佛手柑芬芳，甜而不腻

**经典系列**

- 红丝绒蛋糕｜丝绒可可胚配奶油芝士霜，咸香柔滑
- 提拉米苏｜咖啡酒浸手指饼干，马斯卡彭芝士，浓郁意式风情
- 日式轻乳酪蛋糕｜云朵般轻盈，入口即化，奶香悠长

**鲜果系列**

- 芒果慕斯蛋糕｜台农芒果果肉，椰香胚底，热带风情
- 草莓鲜奶油蛋糕｜当季草莓配北海道奶油，粉嫩清爽
- 蓝莓芝士蛋糕｜重乳酪配野生蓝莓果馅，果酸解腻

我们还支持高端私人定制哦，把您期望的甜品、数量都告诉我吧~"""

UNSUPPORTED_ORDER_REPLY = (
    "我们这里不支持这种类型的，您想订蛋糕吗？我们菜单如下\n\n"
    + MENU_INTRODUCTION_TEXT
)

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
    extras = dict(analysis.extra_requirements)
    pieces_per_box = extras.pop("pieces_per_box", None)
    if pieces_per_box is None:
        pieces_per_box = extras.pop("pieces_per_set", None)

    for key, value in extras.items():
        normalized_key_name = str(key).strip().lower()
        if normalized_key_name in IGNORED_EXTRA_REQUIREMENT_KEYS:
            continue
        normalized_key = EXTRA_FIELD_ALIASES.get(
            normalized_key_name,
            key,
        )
        requirements[normalized_key] = value
    if pieces_per_box is not None:
        pieces = _parse_chinese_count(str(pieces_per_box))
        if pieces is not None:
            requirements["规格"] = f"一套{_format_chinese_count(pieces)}个"
            flavor = requirements.get("flavor")
            if (
                analysis.scenario == "cake"
                and requirements.get("product_name") in (None, "", "蛋糕")
                and flavor
            ):
                requirements["product_name"] = f"{flavor}小蛋糕"

    if (
        analysis.scenario == "cake"
        and requirements.get("product_name") not in (None, "", "蛋糕")
        and str(requirements["product_name"]).endswith("蛋糕")
        and not str(requirements["product_name"]).endswith("小蛋糕")
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


def format_quote_request(
    requirements: dict[str, Any],
    amount: Decimal | int | float | str,
    *,
    order_number: str | None = None,
    note: str | None = None,
    scenario: str = "cake",
) -> str:
    lines = [f"店主报价：{format_amount(amount)} 元"]
    if order_number:
        lines.append(f"订单号：{order_number}")
    if note and note.strip():
        lines.append(f"店主备注：{note.strip()}")
    lines.extend(["", "订单信息：", format_order_summary(requirements, scenario)])
    lines.extend(
        [
            "",
            "请回复“确认报价”接受，或回复“不接受”让店主重新报价。",
        ]
    )
    return "\n".join(lines)


def format_quote_accepted_message(
    *,
    deposit_required: bool,
    deposit_amount: Decimal | int | float | str | None,
) -> str:
    if deposit_required and deposit_amount is not None:
        return (
            f"已确认报价。本单需要支付定金 {format_amount(deposit_amount)} 元，"
            "店主收到定金后会开始制作。"
        )
    return "已确认报价，订单已进入制作。"


def format_amount(
    value: Decimal | int | float | str | None,
) -> str:
    if value is None:
        return "-"
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    text = format(decimal, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def extract_order_reference(content: str) -> str | None:
    text = (content or "").strip()
    if not text:
        return None

    display_match = re.search(
        r"\b(\d{1,2}[.\-]\d{1,2}-\d{1,4})\b",
        text,
    )
    if display_match:
        return display_match.group(1)

    patterns = (
        r"(?:订单号|订单|单号|#)\s*[:：]?\s*(\d{1,4})",
        r"(?:确认报价|确认订单|不接受|拒绝报价|取消订单)"
        r"\s*[:：]?\s*(\d{1,4})",
        r"(\d{1,4})\s*号(?:订单)?",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def extract_customer_note(content: str) -> str | None:
    text = (content or "").strip()
    for marker in ("备注", "留言"):
        index = text.find(marker)
        if index < 0:
            continue
        note = text[index + len(marker) :].lstrip("：:，, ")
        if note:
            return note.strip()
    return None


def is_clear_context_command(content: str) -> bool:
    normalized = (content or "").replace(" ", "")
    return any(
        keyword in normalized
        for keyword in (
            "清除记忆",
            "清空记忆",
            "清除记录",
            "清空记录",
            "删除记录",
            "重新开始",
        )
    )


def is_nonsense_order_message(content: str) -> bool:
    normalized = (content or "").replace(" ", "")
    if any(
        keyword in normalized
        for keyword in NONSENSE_PRODUCT_KEYWORDS
    ) and any(
        keyword in normalized
        for keyword in ("蛋糕", "订", "做", "买", "配送", "取货", "要")
    ):
        return True
    return (
        any(
            keyword in normalized
            for keyword in NONSENSE_DELIVERY_KEYWORDS
        )
        and any(
            keyword in normalized
            for keyword in ("送", "配送", "订", "做", "买", "要", "蛋糕")
        )
    ) or bool(
        re.search(
            r"(?:送到|配送到|送去|运到)"
            r"(?:南极|北极)"
            r"(?!路|街|区|县|市|省|镇|村|号)",
            normalized,
        )
    )


def is_menu_introduction_message(content: str) -> bool:
    normalized = (content or "").strip().lower().replace(" ", "")
    if not normalized:
        return False
    if any(keyword in normalized for keyword in MENU_BYPASS_KEYWORDS):
        return False
    if any(
        keyword in normalized
        for keyword in (
            "我想订",
            "我要订",
            "订一个",
            "订个",
            "预订",
            "下单",
            "我要买",
            "买一个",
            "买一盒",
            "做个",
            "做一个",
            "来一个",
            "要一个",
            "送到",
            "配送",
            "取货",
        )
    ):
        return False

    if any(
        keyword in normalized
        for keyword in (
            "你好",
            "您好",
            "嗨",
            "哈喽",
            "hello",
            "hi",
            "在吗",
            "在不在",
        )
    ):
        return True

    return any(
        keyword in normalized
        for keyword in (
            "有什么蛋糕",
            "有哪些蛋糕",
            "有什么甜品",
            "有哪些甜品",
            "有什么产品",
            "有哪些产品",
            "有什么吃的",
            "有哪些吃的",
            "蛋糕有哪些",
            "甜品有哪些",
            "菜单",
            "推荐",
            "介绍一下",
            "卖什么",
        )
    )


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
    return (
        FIELD_LABELS.get(field)
        or EXTRA_FIELD_LABELS.get(field)
        or field
    )


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

    day_match = re.match(
        r"([0-9一二两三四五六七八九十]+)\s*天(?:后|以后)",
        cleaned,
    )
    if day_match:
        offset = _parse_chinese_count(day_match.group(1))
        if offset is not None:
            target = now + timedelta(days=offset)
            return f"({target.month}.{target.day}){cleaned}"

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


def parse_order_datetime(
    value: str | None,
    now: datetime,
) -> datetime | None:
    if not value:
        return None

    current = now
    target_date = current.date()
    text = value.strip()
    date_recognized = False
    date_match = re.match(
        r"^\((\d{1,2})\.(\d{1,2})\)",
        text,
    )
    if date_match:
        date_recognized = True
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        target_date = current.date().replace(month=month, day=day)
        if target_date < current.date():
            target_date = target_date.replace(year=current.year + 1)
    else:
        day_match = re.match(
            r"([0-9一二两三四五六七八九十]+)\s*天(?:后|以后)",
            text,
        )
        if day_match:
            offset = _parse_chinese_count(day_match.group(1))
            if offset is not None:
                date_recognized = True
                target_date = current.date() + timedelta(days=offset)
        if day_match is None or offset is None:
            for prefix, offset in (
                ("今天", 0),
                ("明天", 1),
                ("后天", 2),
                ("大后天", 3),
            ):
                if text.startswith(prefix):
                    date_recognized = True
                    target_date = current.date() + timedelta(days=offset)
                    break

    time_match = re.search(
        r"(上午|中午|下午|晚上)?\s*"
        r"([一二两三四五六七八九十\d]{1,3})\s*点"
        r"(?:(\d{1,2})分?|半)?",
        value,
    )
    if time_match:
        period = time_match.group(1) or ""
        hour = _parse_chinese_hour(time_match.group(2))
        minute_text = time_match.group(3)
        minute = 30 if "半" in value else int(minute_text or 0)
    else:
        clock_match = re.search(
            r"(?:上午|中午|下午|晚上)?\s*(\d{1,2}):(\d{2})",
            value,
        )
        if not clock_match:
            if not date_recognized:
                return None
            hour = 0
            minute = 0
            period = ""
        else:
            period = ""
            hour = int(clock_match.group(1))
            minute = int(clock_match.group(2))

    if period in {"下午", "晚上"} and hour < 12:
        hour += 12
    elif period == "中午" and hour < 12:
        hour += 12
    elif period == "上午" and hour == 12:
        hour = 0

    return datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        minute,
        tzinfo=current.tzinfo,
    )


def _parse_chinese_hour(value: str) -> int:
    if value.isdigit():
        return int(value)
    numerals = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if value in numerals:
        return numerals[value]
    if value.startswith("十") and value[1:] in numerals:
        return 10 + numerals[value[1:]]
    if value.endswith("十") and value[:-1] in numerals:
        return numerals[value[:-1]] * 10
    return 0


def _parse_chinese_count(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    numerals = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if value in numerals:
        return numerals[value]
    if "十" in value:
        tens_text, ones_text = value.split("十", 1)
        tens = numerals.get(tens_text, 1)
        ones = numerals.get(ones_text, 0) if ones_text else 0
        return tens * 10 + ones
    return None


def _format_chinese_count(value: int) -> str:
    numerals = {
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "七",
        8: "八",
        9: "九",
        10: "十",
    }
    return numerals.get(value, str(value))
