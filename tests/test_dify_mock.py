from app.clients.dify import MockDifyClient


def test_mock_dify_returns_dinner_intent() -> None:
    result = MockDifyClient().run({"content": "周六晚上一起吃饭吗？"})

    assert result.success is True
    assert result.outputs["intent"] == "create_dinner"
    assert result.outputs["activity_title"] == "周末聚餐"


def test_mock_dify_returns_unknown_for_other_text() -> None:
    result = MockDifyClient().run({"content": "今天天气不错"})

    assert result.success is True
    assert result.outputs["intent"] == "unknown"


def test_mock_dify_extracts_preferences() -> None:
    result = MockDifyClient().run(
        {"content": "我周六晚上可以，想吃火锅，预算80，不要香菜"}
    )

    assert result.outputs["intent"] == "provide_preference"
    assert result.outputs["available_time"] == "周六"
    assert result.outputs["cuisine_preference"] == "火锅"
    assert result.outputs["budget_max"] == 80
    assert result.outputs["notes"] == "不要香菜"
