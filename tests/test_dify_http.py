import httpx

from app.clients.dify import HttpDifyClient


def test_http_dify_client_returns_workflow_outputs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/workflows/run"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "succeeded",
                    "outputs": {
                        "intent": "create_dinner",
                        "activity_title": "周五聚餐",
                        "reply": "收到",
                    },
                }
            },
        )

    client = HttpDifyClient(
        api_base="https://dify.example/v1",
        api_key="test-key",
        user="test-user",
        transport=httpx.MockTransport(handler),
    )

    result = client.run({"content": "周五约饭"})

    assert result.success is True
    assert result.outputs["intent"] == "create_dinner"
    assert result.outputs["activity_title"] == "周五聚餐"


def test_http_dify_client_returns_error_on_http_failure() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    client = HttpDifyClient(
        api_base="https://dify.example/v1",
        api_key="test-key",
        user="test-user",
        transport=httpx.MockTransport(handler),
    )

    result = client.run({"content": "周五约饭"})

    assert result.success is False
    assert "Dify request failed" in result.error
