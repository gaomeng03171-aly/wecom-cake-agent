import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx


def print_json(title: str, payload: object) -> None:
    print(f"\n{title}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    payload: dict | None = None,
) -> dict | list:
    response = client.request(method, url, json=payload)
    if response.status_code not in {200, 404, 409}:
        raise RuntimeError(
            f"{method} {url} failed: {response.status_code} {response.text}"
        )
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the dinner agent demo flow.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="FastAPI base URL.",
    )
    parser.add_argument(
        "--admin-key",
        default=os.getenv("ADMIN_API_KEY", ""),
        help="Optional X-Admin-Key value for admin endpoints.",
    )
    args = parser.parse_args()

    headers = {}
    if args.admin_key:
        headers["X-Admin-Key"] = args.admin_key

    run_id = uuid4().hex[:8]
    group_id = f"demo-dinner-{run_id}"
    group_name = f"周末聚餐演示群-{run_id}"

    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=20.0,
        headers=headers,
    ) as client:
        try:
            health = request_json(client, "GET", "/health")
        except httpx.HTTPError as exc:
            print(f"无法连接 FastAPI：{exc}")
            print("请先启动服务：")
            print(
                r".\.venv\Scripts\python.exe -m uvicorn app.main:app "
                r"--app-dir src --host 127.0.0.1 --port 8000"
            )
            return 1

        print("[1/8] 健康检查")
        print_json("服务状态", health)

        create_response = request_json(
            client,
            "POST",
            "/wecom/messages",
            {
                "msg_id": f"{run_id}-create",
                "group_id": group_id,
                "group_name": group_name,
                "sender_id": "demo-user-001",
                "sender_name": "张三",
                "msg_type": "text",
                "content": "周六约饭",
            },
        )
        activity = create_response["activity"]
        activity_id = activity["id"]
        print(f"\n[2/8] 创建活动：activity_id={activity_id}")

        for index, (user_id, user_name, content) in enumerate(
            [
                (
                    "demo-user-002",
                    "李四",
                    "我周六晚上可以，想吃火锅，预算80，不要香菜",
                ),
                (
                    "demo-user-003",
                    "王五",
                    "我周日晚上有空，想吃川菜，预算100",
                ),
            ],
            start=1,
        ):
            request_json(
                client,
                "POST",
                "/wecom/messages",
                {
                    "msg_id": f"{run_id}-preference-{index}",
                    "group_id": group_id,
                    "group_name": group_name,
                    "sender_id": user_id,
                    "sender_name": user_name,
                    "msg_type": "text",
                    "content": content,
                },
            )
        print("[3/8] 已收集两位参与者的时间和口味偏好")

        generate_response = request_json(
            client,
            "POST",
            "/wecom/messages",
            {
                "msg_id": f"{run_id}-generate",
                "group_id": group_id,
                "group_name": group_name,
                "sender_id": "demo-user-001",
                "sender_name": "张三",
                "msg_type": "text",
                "content": "生成方案",
            },
        )
        proposals = generate_response["proposals"]
        print_json("候选方案", proposals)

        voting = request_json(
            client,
            "POST",
            f"/activities/{activity_id}/start-voting",
        )
        print(f"\n[4/8] 开始投票：status={voting['status']}")

        vote_payloads = [
            ("demo-user-001", "张三", "我选1"),
            ("demo-user-002", "李四", "我选1"),
            ("demo-user-003", "王五", "我选2"),
        ]
        for index, (user_id, user_name, content) in enumerate(
            vote_payloads,
            start=1,
        ):
            request_json(
                client,
                "POST",
                "/wecom/messages",
                {
                    "msg_id": f"{run_id}-vote-{index}",
                    "group_id": group_id,
                    "group_name": group_name,
                    "sender_id": user_id,
                    "sender_name": user_name,
                    "msg_type": "text",
                    "content": content,
                },
            )
        print("[5/8] 三位成员已完成投票")

        confirmed = request_json(
            client,
            "POST",
            f"/activities/{activity_id}/confirm",
        )
        print(f"\n[6/8] 最终方案：{confirmed['confirmed_plan']}")

        due_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        reminder = request_json(
            client,
            "POST",
            f"/activities/{activity_id}/reminders",
            {
                "reminder_type": "custom",
                "content": "演示提醒：聚餐安排已确认。",
                "scheduled_at": due_at.isoformat(),
            },
        )
        dispatched = request_json(
            client,
            "POST",
            "/reminders/dispatch-due",
        )
        print_json("提醒发送结果", {"created": reminder, "dispatched": dispatched})

        detail = request_json(
            client,
            "GET",
            f"/admin/activities/{activity_id}",
        )
        print_json(
            "[7/8] 管理详情摘要",
            {
                "activity": detail["activity"],
                "participants": len(detail["participants"]),
                "proposals": len(detail["proposals"]),
                "votes": len(detail["votes"]),
                "outbox": [
                    {
                        "id": message["id"],
                        "status": message["status"],
                        "content": message["content"],
                    }
                    for message in detail["outbox_messages"]
                ],
                "reminders": [
                    {
                        "id": reminder_item["id"],
                        "status": reminder_item["status"],
                    }
                    for reminder_item in detail["reminders"]
                ],
            },
        )
        print("\n[8/8] 演示完成")
        return 0


if __name__ == "__main__":
    sys.exit(main())
