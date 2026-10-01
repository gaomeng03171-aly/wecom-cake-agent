from datetime import datetime, timedelta, timezone


def _create_activity(client, msg_id: str, group_id: str) -> int:
    response = client.post(
        "/wecom/messages",
        json={
            "msg_id": msg_id,
            "group_id": group_id,
            "group_name": "提醒测试群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "周六约饭",
        },
    )
    assert response.status_code == 200
    return response.json()["activity"]["id"]


def test_due_reminder_is_sent_through_outbox(client) -> None:
    activity_id = _create_activity(
        client,
        "wecom-reminder-001",
        "reminder-group-001",
    )
    scheduled_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    create_response = client.post(
        f"/activities/{activity_id}/reminders",
        json={
            "reminder_type": "voting_deadline",
            "content": "投票将在十分钟后截止，请尽快选择方案。",
            "scheduled_at": scheduled_at.isoformat(),
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["status"] == "pending"

    dispatch_response = client.post("/reminders/dispatch-due")
    assert dispatch_response.status_code == 200
    reminders = dispatch_response.json()
    assert len(reminders) == 1
    assert reminders[0]["status"] == "sent"
    assert reminders[0]["sent_at"] is not None

    second_dispatch = client.post("/reminders/dispatch-due")
    assert second_dispatch.status_code == 200
    assert second_dispatch.json() == []

    outbox_response = client.get(
        "/outbox",
        params={"group_id": "reminder-group-001"},
    )
    assert outbox_response.status_code == 200
    assert outbox_response.json()[0]["status"] == "sent"
    assert "投票将在十分钟后截止" in outbox_response.json()[0]["content"]


def test_future_reminder_is_not_dispatched(client) -> None:
    activity_id = _create_activity(
        client,
        "wecom-reminder-002",
        "reminder-group-002",
    )
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)

    response = client.post(
        f"/activities/{activity_id}/reminders",
        json={
            "reminder_type": "activity_start",
            "content": "聚餐将在两小时后开始。",
            "scheduled_at": scheduled_at.isoformat(),
        },
    )
    assert response.status_code == 200

    dispatch_response = client.post("/reminders/dispatch-due")
    assert dispatch_response.status_code == 200
    assert dispatch_response.json() == []


def test_pending_reminder_can_be_cancelled(client) -> None:
    activity_id = _create_activity(
        client,
        "wecom-reminder-003",
        "reminder-group-003",
    )
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)

    create_response = client.post(
        f"/activities/{activity_id}/reminders",
        json={
            "reminder_type": "custom",
            "content": "自定义提醒",
            "scheduled_at": scheduled_at.isoformat(),
        },
    )
    reminder_id = create_response.json()["id"]

    cancel_response = client.post(f"/reminders/{reminder_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_activity_schedule_creates_default_reminders(client) -> None:
    activity_id = _create_activity(
        client,
        "wecom-reminder-004",
        "reminder-group-004",
    )
    deadline_at = datetime.now(timezone.utc) + timedelta(hours=2)
    start_at = datetime.now(timezone.utc) + timedelta(hours=4)

    response = client.post(
        f"/activities/{activity_id}/schedule-reminders",
        json={
            "deadline_at": deadline_at.isoformat(),
            "start_at": start_at.isoformat(),
        },
    )

    assert response.status_code == 200
    reminders = response.json()
    assert len(reminders) == 2
    assert {reminder["reminder_type"] for reminder in reminders} == {
        "voting_deadline",
        "activity_start",
    }
