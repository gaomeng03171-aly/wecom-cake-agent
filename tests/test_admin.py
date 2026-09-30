from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


def _post_message(
    client,
    msg_id: str,
    group_id: str,
    sender_id: str,
    sender_name: str,
    content: str,
):
    return client.post(
        "/wecom/messages",
        json={
            "msg_id": msg_id,
            "group_id": group_id,
            "group_name": "管理测试群",
            "sender_id": sender_id,
            "sender_name": sender_name,
            "msg_type": "text",
            "content": content,
        },
    )


def _build_activity_data(client, group_id: str) -> int:
    create_response = _post_message(
        client,
        "admin-msg-001",
        group_id,
        "user-001",
        "张三",
        "周六约饭",
    )
    activity_id = create_response.json()["activity"]["id"]

    _post_message(
        client,
        "admin-msg-002",
        group_id,
        "user-002",
        "李四",
        "我周六晚上可以，想吃火锅，预算80",
    )
    _post_message(
        client,
        "admin-msg-003",
        group_id,
        "user-001",
        "张三",
        "生成方案",
    )
    client.post(f"/activities/{activity_id}/start-voting")
    _post_message(
        client,
        "admin-msg-004",
        group_id,
        "user-001",
        "张三",
        "我选1",
    )
    _post_message(
        client,
        "admin-msg-005",
        group_id,
        "user-002",
        "李四",
        "我选2",
    )

    deadline_at = datetime.now(timezone.utc) + timedelta(hours=2)
    start_at = datetime.now(timezone.utc) + timedelta(hours=4)
    client.post(
        f"/activities/{activity_id}/schedule-reminders",
        json={
            "deadline_at": deadline_at.isoformat(),
            "start_at": start_at.isoformat(),
        },
    )
    return activity_id


def test_admin_overview_returns_current_counts(client) -> None:
    _build_activity_data(client, "admin-group-001")

    response = client.get("/admin/overview")

    assert response.status_code == 200
    overview = response.json()
    assert overview["total_activities"] == 1
    assert overview["active_activities"] == 1
    assert overview["participants"] == 2
    assert overview["proposals"] == 3
    assert overview["votes"] == 2
    assert overview["reminders_pending"] == 2
    assert overview["outbox_sent"] >= 5


def test_admin_activity_detail_aggregates_business_data(client) -> None:
    activity_id = _build_activity_data(client, "admin-group-002")

    response = client.get(f"/admin/activities/{activity_id}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["activity"]["status"] == "voting"
    assert len(detail["participants"]) == 2
    assert len(detail["proposals"]) == 3
    assert len(detail["votes"]) == 2
    assert len(detail["reminders"]) == 2
    assert len(detail["outbox_messages"]) >= 5


def test_admin_messages_can_be_filtered_by_group(client) -> None:
    group_id = "admin-group-003"
    _build_activity_data(client, group_id)

    response = client.get("/admin/messages", params={"group_id": group_id})

    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 5
    assert all(message["group_id"] == group_id for message in messages)


def test_admin_unknown_activity_returns_404(client) -> None:
    response = client.get("/admin/activities/999999")

    assert response.status_code == 404


def test_admin_api_key_is_enforced_when_configured(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.admin.get_settings",
        lambda: SimpleNamespace(admin_api_key="secret"),
    )

    unauthorized = client.get("/admin/overview")
    assert unauthorized.status_code == 401

    authorized = client.get(
        "/admin/overview",
        headers={"X-Admin-Key": "secret"},
    )
    assert authorized.status_code == 200
