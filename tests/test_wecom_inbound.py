def test_wecom_message_is_stored_and_deduplicated(client) -> None:
    payload = {
        "msg_id": "wecom-msg-001",
        "group_id": "group-001",
        "group_name": "周末聚餐群",
        "sender_id": "user-001",
        "sender_name": "张三",
        "msg_type": "text",
        "content": "周六晚上一起吃饭吗？",
    }

    first = client.post("/wecom/messages", json=payload)
    second = client.post("/wecom/messages", json=payload)

    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["accepted"] is True
    assert first_payload["duplicate"] is False
    assert first_payload["message_id"] == 1
    assert first_payload["dify_error"] is None
    assert first_payload["analysis"]["intent"] == "create_dinner"
    assert first_payload["activity"]["status"] == "collecting"

    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["accepted"] is True
    assert second_payload["duplicate"] is True
    assert second_payload["message_id"] == 1
    assert second_payload["analysis"] is None
    assert second_payload["outbox"] is None
    assert second_payload["activity"] is None


def test_wecom_message_requires_msg_id(client) -> None:
    response = client.post(
        "/wecom/messages",
        json={
            "group_id": "group-001",
            "sender_id": "user-001",
            "content": "缺少消息 ID",
        },
    )

    assert response.status_code == 422
