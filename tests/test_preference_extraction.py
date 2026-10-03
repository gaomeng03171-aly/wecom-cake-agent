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


def test_preference_message_updates_participant(client) -> None:
    activity_id = _create_activity(
        client,
        "wecom-preference-001",
        "preference-group-001",
    )

    preference_response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-preference-002",
            "group_id": "preference-group-001",
            "group_name": "周末聚餐群",
            "sender_id": "user-002",
            "sender_name": "李四",
            "msg_type": "text",
            "content": "我周六晚上可以，想吃火锅，预算80，不要香菜",
        },
    )

    assert preference_response.status_code == 200
    analysis = preference_response.json()["analysis"]
    assert analysis["intent"] == "provide_preference"
    assert analysis["available_time"] == "周六"
    assert analysis["cuisine_preference"] == "火锅"
    assert analysis["budget_max"] == 80
    assert analysis["notes"] == "不要香菜"

    participants = client.get(f"/activities/{activity_id}/participants").json()
    target = next(
        participant
        for participant in participants
        if participant["user_id"] == "user-002"
    )
    assert target["available_time"] == "周六"
    assert target["cuisine_preference"] == "火锅"
    assert target["budget_max"] == 80
    assert target["notes"] == "不要香菜"


def test_preference_without_active_activity_creates_activity(client) -> None:
    response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-preference-003",
            "group_id": "preference-group-002",
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "我想吃火锅",
        },
    )

    assert response.status_code == 200
    assert response.json()["analysis"]["intent"] == "provide_preference"
    assert response.json()["activity"] is not None
    assert response.json()["activity"]["status"] == "collecting"
    assert response.json()["participant"]["user_id"] == "user-001"
    assert response.json()["participant"]["cuisine_preference"] == "火锅"
