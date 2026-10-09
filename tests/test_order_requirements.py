from datetime import datetime
from zoneinfo import ZoneInfo

from app.schemas.dify import OrderDifyOutput
from app.services.order_requirements import (
    annotate_relative_time,
    build_order_requirements,
    extract_customer_note,
    extract_order_reference,
    format_order_confirmation,
    format_order_summary,
    format_quote_request,
    is_menu_introduction_message,
    is_nonsense_order_message,
    parse_order_datetime,
)


def test_annotate_relative_time_with_current_date() -> None:
    now = datetime(2026, 10, 6, 10, 0, tzinfo=ZoneInfo("Asia/Hong_Kong"))

    assert (
        annotate_relative_time("今天下午五点", now)
        == "(10.6)今天下午五点"
    )
    assert (
        annotate_relative_time("明天下午三点", now)
        == "(10.7)明天下午三点"
    )
    assert (
        annotate_relative_time("五天后的下午一点", now)
        == "(10.11)五天后的下午一点"
    )


def test_confirmation_asks_for_cake_message_or_notes() -> None:
    text = format_order_confirmation(
        {
            "customer_name": "张三",
            "phone": "13800138000",
            "product_name": "蛋糕",
            "quantity": 1,
            "size": "8寸",
            "flavor": "草莓",
            "pickup_time": "(10.6)今天下午五点",
        }
    )

    assert "是否需要补充蛋糕留言或备注" in text


def test_extract_order_reference_from_customer_message() -> None:
    assert extract_order_reference("确认报价 0006") == "0006"
    assert extract_order_reference("确认报价 10.07-0006") == "10.07-0006"
    assert extract_order_reference("订单号：6 不接受") == "6"
    assert extract_order_reference("6号订单取消") == "6"


def test_customer_note_is_extracted_and_extra_fields_are_chinese() -> None:
    assert extract_customer_note("备注需要十八根蜡烛") == "需要十八根蜡烛"
    assert extract_customer_note("留言：请写生日快乐") == "请写生日快乐"
    assert "蜡烛数量：18" in format_order_summary({"candles": 18})


def test_quote_request_includes_owner_note() -> None:
    text = format_quote_request(
        {"product_name": "蛋糕"},
        188,
        note="亲亲给您打了八折",
    )

    assert "店主备注：亲亲给您打了八折" in text


def test_known_extra_requirement_keys_are_normalized_to_chinese() -> None:
    requirements = build_order_requirements(
        OrderDifyOutput(
            intent="provide_requirement",
            extra_requirements={"candles": 18},
        )
    )

    assert requirements["蜡烛数量"] == 18
    assert "candles" not in requirements


def test_internal_request_type_is_not_saved_as_requirement() -> None:
    requirements = build_order_requirements(
        OrderDifyOutput(
            intent="provide_requirement",
            extra_requirements={
                "request_type": "order_status_query",
                "candles": 18,
            },
        )
    )

    assert "request_type" not in requirements
    assert "request_type：order_status_query" not in format_order_summary(
        requirements
    )
    assert requirements["蜡烛数量"] == 18


def test_parse_order_datetime_supports_days_later() -> None:
    now = datetime(2026, 10, 8, 9, 0, tzinfo=ZoneInfo("Asia/Hong_Kong"))

    assert parse_order_datetime("五天后的下午一点", now) == datetime(
        2026,
        10,
        13,
        13,
        0,
        tzinfo=now.tzinfo,
    )


def test_parse_order_datetime_supports_date_without_time() -> None:
    now = datetime(2026, 10, 9, 9, 0, tzinfo=ZoneInfo("Asia/Hong_Kong"))

    assert parse_order_datetime("(10.19)十天后取货", now) == datetime(
        2026,
        10,
        19,
        0,
        0,
        tzinfo=now.tzinfo,
    )


def test_menu_bypasses_order_operations_and_keeps_real_addresses() -> None:
    assert is_menu_introduction_message("你好") is True
    assert is_menu_introduction_message("你好，确认报价") is False
    assert is_menu_introduction_message("你好，太贵了") is False
    assert is_menu_introduction_message("你好，取消订单") is False
    assert is_nonsense_order_message("送到南极路 88 号") is False
    assert is_nonsense_order_message("送到月球") is True
