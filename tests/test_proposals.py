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


def _add_preference(client, group_id: str) -> None:
    response = client.post(
        "/wecom/messages",
        json={
            "msg_id": f"preference-{group_id}",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-002",
            "sender_name": "李四",
            "msg_type": "text",
            "content": "我周六晚上可以，想吃火锅，预算80，不要香菜",
        },
    )
    assert response.status_code == 200


def test_generate_proposals_and_vote_flow(client) -> None:
    group_id = "proposal-group-001"
    activity_id = _create_activity(
        client,
        "wecom-proposal-001",
        group_id,
    )
    _add_preference(client, group_id)

    generate_response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-proposal-002",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "生成方案",
        },
    )

    assert generate_response.status_code == 200
    generate_payload = generate_response.json()
    assert generate_payload["analysis"]["intent"] == "generate_proposals"
    assert generate_payload["activity"]["status"] == "voting"
    assert len(generate_payload["proposals"]) == 3
    assert "1. " in generate_payload["outbox"]["content"]
    assert "我选1" in generate_payload["outbox"]["content"]

    start_response = client.post(f"/activities/{activity_id}/start-voting")
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "voting"

    first_vote = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-vote-001",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "我选1",
        },
    )
    assert first_vote.status_code == 200
    assert first_vote.json()["vote"]["proposal_id"] == 1

    second_vote = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-vote-002",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-002",
            "sender_name": "李四",
            "msg_type": "text",
            "content": "我选2",
        },
    )
    assert second_vote.status_code == 200
    assert second_vote.json()["vote"]["proposal_id"] == 2

    confirm_response = client.post(f"/activities/{activity_id}/confirm")
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"
    assert confirm_response.json()["confirmed_plan"] is not None


def test_generate_proposals_requires_participants(client) -> None:
    activity_id = _create_activity(
        client,
        "wecom-proposal-003",
        "proposal-group-002",
    )

    # Remove the only participant, then attempt generation.
    leave_response = client.post(
        f"/activities/{activity_id}/participants/user-001/leave"
    )
    assert leave_response.status_code == 200

    response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-proposal-004",
            "group_id": "proposal-group-002",
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "生成方案",
        },
    )

    assert response.status_code == 200
    assert response.json()["dify_error"] == "no active participants"


def test_vote_choice_maps_to_current_activity_proposal(client) -> None:
    first_group = "proposal-group-003"
    first_activity_id = _create_activity(client, "wecom-proposal-005", first_group)
    _add_preference(client, first_group)
    client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-proposal-006",
            "group_id": first_group,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "生成方案",
        },
    )

    second_group = "proposal-group-004"
    second_activity_id = _create_activity(client, "wecom-proposal-007", second_group)
    _add_preference(client, second_group)
    generate_response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-proposal-008",
            "group_id": second_group,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "生成方案",
        },
    )
    second_proposals = generate_response.json()["proposals"]
    client.post(f"/activities/{second_activity_id}/start-voting")

    vote_response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-vote-003",
            "group_id": second_group,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "我选1",
        },
    )

    assert first_activity_id != second_activity_id
    assert vote_response.status_code == 200
    assert vote_response.json()["vote"]["proposal_id"] == second_proposals[0]["id"]


def test_summary_and_confirm_commands_return_final_result(client) -> None:
    group_id = "proposal-group-005"
    activity_id = _create_activity(client, "wecom-proposal-009", group_id)
    _add_preference(client, group_id)
    client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-proposal-010",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "生成方案",
        },
    )
    client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-vote-004",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "我选1",
        },
    )
    client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-vote-005",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-002",
            "sender_name": "李四",
            "msg_type": "text",
            "content": "我选2",
        },
    )

    summary = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-summary-001",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "总结刚刚的方案结果",
        },
    )

    assert summary.status_code == 200
    assert "当前投票结果" in summary.json()["outbox"]["content"]
    assert "确认方案" in summary.json()["outbox"]["content"]

    confirmation = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-confirm-001",
            "group_id": group_id,
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "确认方案",
        },
    )

    assert confirmation.status_code == 200
    assert confirmation.json()["activity"]["id"] == activity_id
    assert confirmation.json()["activity"]["status"] == "confirmed"
    assert "最终方案已确认" in confirmation.json()["outbox"]["content"]
