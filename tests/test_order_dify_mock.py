from app.clients.dify import MockDifyClient, get_order_dify_client
from app.services.dify import analyze_order_message


def test_order_dify_defaults_to_mock_client() -> None:
    assert isinstance(get_order_dify_client(), MockDifyClient)


def test_mock_order_extracts_complete_cake_order() -> None:
    analysis = analyze_order_message(
        "我叫张三，电话13800138000，我想订一个8寸草莓蛋糕，"
        "明天下午三点取，预算200，写着生日快乐"
    )

    assert analysis.intent == "create_order"
    assert analysis.scenario == "cake"
    assert analysis.requirements["customer_name"] == "张三"
    assert analysis.requirements["phone"] == "13800138000"
    assert analysis.requirements["product_name"] == "蛋糕"
    assert analysis.requirements["quantity"] == 1
    assert analysis.requirements["size"] == "8寸"
    assert analysis.requirements["flavor"] == "草莓"
    assert analysis.requirements["pickup_time"].startswith("(")
    assert analysis.requirements["pickup_time"].endswith("明天下午三点")
    assert analysis.requirements["budget_max"] == 200
    assert analysis.customer_expected_price == 200
    assert analysis.customer_expected_price_text == "200元"
    assert analysis.requirements["message_on_cake"] == "生日快乐"
    assert analysis.missing_fields == []
    assert analysis.confirmation_text is not None
    assert "请确认订单信息" in analysis.reply
    assert "蛋糕留言或备注" in analysis.reply


def test_mock_order_generates_follow_up_for_missing_fields() -> None:
    analysis = analyze_order_message("我想订一个蛋糕")

    assert analysis.intent == "create_order"
    assert analysis.requirements["product_name"] == "蛋糕"
    assert analysis.requirements["quantity"] == 1
    assert "customer_name" in analysis.missing_fields
    assert "phone" in analysis.missing_fields
    assert "size" in analysis.missing_fields
    assert "flavor" in analysis.missing_fields
    assert "pickup_time" in analysis.missing_fields
    assert "还需要确认" in analysis.reply


def test_mock_order_keeps_red_velvet_and_set_quantity() -> None:
    analysis = analyze_order_message(
        "我要买一盒红丝绒小蛋糕，一盒里装四个，草莓味的"
    )

    assert analysis.requirements["product_name"] == "红丝绒小蛋糕"
    assert analysis.requirements["规格"] == "一套四个"


def test_mock_order_recognizes_update_confirm_and_cancel() -> None:
    update = analyze_order_message("把口味改成巧克力")
    confirm = analyze_order_message("确认下单")
    cancel = analyze_order_message("取消订单")
    confirm_quote = analyze_order_message("确认报价")
    confirm_quote_with_ref = analyze_order_message("确认报价 10.07-0006")
    reject_quote = analyze_order_message("太贵了，不接受")

    assert update.intent == "update_requirement"
    assert update.requirements["flavor"] == "巧克力"
    assert confirm.intent == "confirm_order"
    assert confirm_quote.intent == "confirm_quote"
    assert confirm_quote_with_ref.order_reference == "10.07-0006"
    assert reject_quote.intent == "reject_quote"
    assert cancel.intent == "cancel_order"
