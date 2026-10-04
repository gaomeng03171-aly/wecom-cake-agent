def test_admin_integration_status_reports_callback_readiness(client) -> None:
    response = client.get("/admin/integration-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["wecom_sender_mode"] == "mock"
    assert payload["wecom_sender_ready"] is True
    assert payload["wecom_callback_ready"] is True
    assert payload["missing_wecom_callback_config"] == []
    assert payload["database_dialect"] == "sqlite"
    assert payload["missing_wecom_aibot_config"] == [
        "WECOM_AIBOT_ID",
        "WECOM_AIBOT_SECRET",
    ]
