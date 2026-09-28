def test_dinner_activity_is_created_from_message(client) -> None:
    response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-activity-001",
            "group_id": "dinner-group-001",
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "周六晚上一起吃饭吗？",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis"]["intent"] == "create_dinner"
    assert payload["activity"]["status"] == "collecting"
    assert payload["activity"]["group_id"] == "dinner-group-001"


def test_dinner_activity_follows_allowed_transitions(client) -> None:
    create_response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-activity-002",
            "group_id": "dinner-group-002",
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "约饭",
        },
    )
    activity_id = create_response.json()["activity"]["id"]

    invalid = client.post(
        f"/activities/{activity_id}/transition",
        json={"status": "confirmed"},
    )
    assert invalid.status_code == 409

    proposing = client.post(
        f"/activities/{activity_id}/transition",
        json={"status": "proposing"},
    )
    assert proposing.status_code == 200
    assert proposing.json()["status"] == "proposing"

    voting = client.post(
        f"/activities/{activity_id}/transition",
        json={"status": "voting"},
    )
    assert voting.status_code == 200
    assert voting.json()["status"] == "voting"

    confirmed = client.post(
        f"/activities/{activity_id}/transition",
        json={"status": "confirmed"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"


def test_only_one_active_activity_per_group(client) -> None:
    first = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-activity-003",
            "group_id": "dinner-group-003",
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "周六约饭",
        },
    )
    first_id = first.json()["activity"]["id"]

    second = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-activity-004",
            "group_id": "dinner-group-003",
            "group_name": "周末聚餐群",
            "sender_id": "user-002",
            "sender_name": "李四",
            "msg_type": "text",
            "content": "我也想发起聚餐",
        },
    )

    assert second.status_code == 200
    assert second.json()["activity"]["id"] == first_id
