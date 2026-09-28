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
