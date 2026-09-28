def _create_activity(client, msg_id: str, group_id: str) -> int:
    response = client.post(
        "/wecom/messages",
        json={
            "msg_id": msg_id,
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "周六约饭",
        },
    )
    assert response.status_code == 200
    return response.json()["activity"]["id"]


def test_initiator_is_added_as_participant(client) -> None:
    activity_id = _create_activity(
        client,
        "wecom-participant-001",
        "participant-group-001",
    )

    response = client.get(f"/activities/{activity_id}/participants")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["user_id"] == "user-001"


def test_participant_can_join_update_and_leave(client) -> None:
    activity_id = _create_activity(
        client,
        "wecom-participant-002",
        "participant-group-002",
    )

    join_response = client.post(
        f"/activities/{activity_id}/participants",
        json={
            "user_id": "user-002",
            "user_name": "李四",
            "available_time": "周六晚上",
            "cuisine_preference": "火锅",
            "budget_max": 80,
            "notes": "不要香菜",
        },
    )
    assert join_response.status_code == 200
    assert join_response.json()["cuisine_preference"] == "火锅"

    update_response = client.put(
        f"/activities/{activity_id}/participants/user-002",
        json={"budget_max": 100, "notes": "可以接受香菜"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["budget_max"] == 100
    assert update_response.json()["notes"] == "可以接受香菜"

    leave_response = client.post(
        f"/activities/{activity_id}/participants/user-002/leave"
    )
    assert leave_response.status_code == 200
    assert leave_response.json()["left_at"] is not None

    active_response = client.get(f"/activities/{activity_id}/participants")
    assert len(active_response.json()) == 1


def test_joining_unknown_activity_returns_404(client) -> None:
    response = client.post(
        "/activities/999999/participants",
        json={"user_id": "user-002", "user_name": "李四"},
    )

    assert response.status_code == 404
