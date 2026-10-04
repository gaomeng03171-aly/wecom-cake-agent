"""Create a WeCom app group chat (cgi-bin/appchat/create).

The created chatid can be used as the outbox group_id; AppWeComSender then
pushes messages to the group via cgi-bin/appchat/send.

Requirements:
- WECOM_SENDER_MODE must be app/real and the app must be visible to the
  root department (企业微信后台强制要求).
- userlist must contain at least 2 valid enterprise userids.
- A freshly created group does not appear in the WeCom client until the app
  sends at least one message into it (done by default; pass --no-test to skip).

Example:
    python scripts/create_wecom_group.py \
        --name "周末约饭群" --userids GaoMeng,WangEr --owner GaoMeng
"""

import argparse
import sys

import httpx

from app.clients.wecom import AppWeComSender
from app.config import get_settings


def _build_sender() -> AppWeComSender:
    settings = get_settings()
    if settings.wecom_sender_mode not in {"app", "real"}:
        print("请先将 WECOM_SENDER_MODE 配置为 app 或 real。")
        raise SystemExit(1)

    missing = []
    if not settings.wecom_corp_id:
        missing.append("WECOM_CORP_ID")
    if not settings.wecom_app_secret:
        missing.append("WECOM_APP_SECRET")
    if not settings.wecom_agent_id:
        missing.append("WECOM_AGENT_ID")
    if missing:
        print("缺少发送配置：" + ", ".join(missing))
        raise SystemExit(1)

    return AppWeComSender(
        corp_id=settings.wecom_corp_id,
        app_secret=settings.wecom_app_secret,
        agent_id=settings.wecom_agent_id,
        api_base=settings.wecom_api_base,
        timeout_seconds=settings.wecom_sender_timeout_seconds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a WeCom self-built app group chat.",
    )
    parser.add_argument("--name", required=True, help="群聊名称")
    parser.add_argument(
        "--userids",
        required=True,
        help="群成员 userid，英文逗号分隔，至少 2 人，例如 GaoMeng,WangEr",
    )
    parser.add_argument("--owner", help="群主 userid（可选，默认取 userlist 第一人）")
    parser.add_argument("--chatid", help="自定义 chatid（可选，不传则由企业微信生成）")
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="创建后不发送首条测试消息（不发消息群不会在客户端显示）",
    )
    args = parser.parse_args()

    userlist = [u.strip() for u in args.userids.split(",") if u.strip()]
    if len(userlist) < 2:
        print("userlist 至少需要 2 个有效 userid（企业微信 appchat/create 限制）。")
        return 1

    sender = _build_sender()
    try:
        access_token = sender.get_access_token()
    except RuntimeError as exc:
        print("token_ok=false")
        print(f"error={exc}")
        return 1

    body: dict[str, object] = {
        "name": args.name,
        "owner": args.owner or userlist[0],
        "userlist": userlist,
    }
    if args.chatid:
        body["chatid"] = args.chatid

    try:
        with httpx.Client(
            base_url="https://qyapi.weixin.qq.com",
            timeout=10.0,
            trust_env=False,
        ) as client:
            response = client.post(
                "cgi-bin/appchat/create",
                params={"access_token": access_token},
                json=body,
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"request_failed={exc}")
        return 1

    if payload.get("errcode") != 0:
        print(f"create_failed errcode={payload.get('errcode')} errmsg={payload.get('errmsg')}")
        print("常见原因：应用可见范围不是根部门；userid 不存在或不在应用可见范围内。")
        return 1

    chatid = payload.get("chatid")
    print("create_ok=true")
    print(f"chatid={chatid}")

    if args.no_test:
        print("已跳过首条消息；注意未下发消息的群不会在企业微信客户端显示。")
        return 0

    try:
        with httpx.Client(
            base_url="https://qyapi.weixin.qq.com",
            timeout=10.0,
            trust_env=False,
        ) as client:
            send_resp = client.post(
                "cgi-bin/appchat/send",
                params={"access_token": access_token},
                json={
                    "chatid": chatid,
                    "msgtype": "text",
                    "text": {"content": f"「{args.name}」已创建，约饭机器人已就位。"},
                },
            )
        send_payload = send_resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"test_message_failed={exc}")
        return 1

    if send_payload.get("errcode") != 0:
        print(
            "test_message_failed "
            f"errcode={send_payload.get('errcode')} errmsg={send_payload.get('errmsg')}"
        )
        return 1

    print("test_message_ok=true（群聊应已出现在成员的企业微信会话列表中）")
    print(f"后续向群发消息：python scripts/debug_wecom_sender.py send --target {chatid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
