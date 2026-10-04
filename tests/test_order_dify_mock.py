from app.clients.dify import MockDifyClient, get_order_dify_client
from app.services.dify import analyze_order_message


def test_order_dify_defaults_to_mock_client() -> None:
    assert isinstance(get_order_dify_client(), MockDifyClient)


def test_mock_order_extracts_complete_cake_order() -> None:
    analysis = analyze_order_message(
        "我想订一个8寸草莓蛋糕，明天下午三点取，预算200，写着生日快乐"
    )

    assert analysis.intent == "create_order"
    assert analysis.scenario == "cake"
    assert analysis.requirements["product_name"] == "蛋糕"
    assert analysis.requirements["quantity"] == 1
    assert analysis.requirements["size"] == "8寸"
    assert analysis.requirements["flavor"] == "草莓"
    assert analysis.requirements["pickup_time"] == "明天下午三点"
    assert analysis.requirements["budget_max"] == 200
    assert analysis.requirements["message_on_cake"] == "生日快乐"
    assert analysis.missing_fields == []
    assert analysis.confirmation_text is not None
    assert "请确认订单信息" in analysis.reply


def test_mock_order_generates_follow_up_for_missing_fields() -> None:
    analysis = analyze_order_message("我想订一个蛋糕")

    assert analysis.intent == "create_order"
    assert analysis.requirements["product_name"] == "蛋糕"
    assert analysis.requirements["quantity"] == 1
    assert "size" in analysis.missing_fields
    assert "flavor" in analysis.missing_fields
    assert "pickup_time" in analysis.missing_fields
    assert "还需要确认" in analysis.reply


def test_mock_order_recognizes_update_confirm_and_cancel() -> None:
    update = analyze_order_message("把口味改成巧克力")
    confirm = analyze_order_message("确认下单")
    cancel = analyze_order_message("取消订单")

    assert update.intent == "update_requirement"
    assert update.requirements["flavor"] == "巧克力"
    assert confirm.intent == "confirm_order"
    assert cancel.intent == "cancel_order"
