import argparse
import sys

from app.clients.wecom import AppWeComSender
from app.config import get_settings
from app.models import OutboxMessage


def _mask_token(token: str) -> str:
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


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
        description="Debug the WeCom self-built app sender.",
    )
    parser.add_argument(
        "mode",
        choices=("token", "send"),
        help="Fetch an access token or send a test message.",
    )
    parser.add_argument(
        "--target",
        help="Group chat id, or direct-{user_id} for a direct message.",
    )
    parser.add_argument("--content", default="wecom-cake-agent 联调测试")
    args = parser.parse_args()

    sender = _build_sender()

    if args.mode == "token":
        try:
            token = sender.get_access_token()
        except RuntimeError as exc:
            print(f"token_ok=false")
            print(f"error={exc}")
            return 1
        print("token_ok=true")
        print(f"access_token_masked={_mask_token(token)}")
        return 0

    if not args.target:
        print("send 模式需要 --target。")
        return 1

    message = OutboxMessage(
        id=0,
        group_id=args.target,
        content=args.content,
        status="pending",
    )
    result = sender.send(message)
    print(f"success={str(result.success).lower()}")
    if result.provider_message_id:
        print(f"provider_message_id={result.provider_message_id}")
    if result.error:
        print(f"error={result.error}")
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
