from app.clients.wecom import SendResult, WeComSender
from app.db import get_session_factory
from app.services.outbox import dispatch_message, enqueue_reply


class FailingSender(WeComSender):
    def send(self, message) -> SendResult:
        return SendResult(success=False, error="simulated send failure")


def test_inbound_message_enqueues_and_sends_reply(client) -> None:
    response = client.post(
        "/wecom/messages",
        json={
            "msg_id": "wecom-outbox-001",
            "group_id": "outbox-group-001",
            "group_name": "周末聚餐群",
            "sender_id": "user-001",
            "sender_name": "张三",
            "msg_type": "text",
            "content": "周六约饭",
        },
    )

    assert response.status_code == 200
    outbox = response.json()["outbox"]
    assert outbox["status"] == "sent"
    assert outbox["provider_message_id"] == f"mock-{outbox['id']}"


def test_pending_outbox_can_be_dispatched_in_batch(client) -> None:
    create_response = client.post(
        "/outbox",
        json={
            "group_id": "outbox-group-002",
            "content": "这是一条待发送消息",
            "dispatch": False,
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["status"] == "pending"

    pending_response = client.get("/outbox", params={"status": "pending"})
    assert pending_response.status_code == 200
    assert len(pending_response.json()) == 1

    dispatch_response = client.post("/outbox/dispatch-pending")
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()[0]["status"] == "sent"


def test_failed_outbox_message_can_be_retried(client) -> None:
    db = get_session_factory()()
    try:
        message = enqueue_reply(
            db,
            group_id="outbox-group-003",
            content="重试测试",
        )
        failed = dispatch_message(db, message.id, sender=FailingSender())
        assert failed.status == "pending"
        assert failed.retry_count == 1
        assert failed.last_error == "simulated send failure"
        message_id = failed.id
    finally:
        db.close()

    retry_response = client.post(f"/outbox/{message_id}/retry")
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "sent"
    assert retry_response.json()["retry_count"] == 0
