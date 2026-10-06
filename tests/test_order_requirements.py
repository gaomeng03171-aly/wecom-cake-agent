from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.order_requirements import (
    annotate_relative_time,
    format_order_confirmation,
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
