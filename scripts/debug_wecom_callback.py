import argparse
import sys
import time
from uuid import uuid4
from xml.etree.ElementTree import Element, SubElement, tostring

import httpx

from app.clients.wecom_crypto import WeComCryptoError, get_wecom_crypto


def build_outer_xml(encrypted: str, corp_id: str) -> str:
    root = Element("xml")
    SubElement(root, "ToUserName").text = corp_id
    SubElement(root, "Encrypt").text = encrypted
    SubElement(root, "AgentID").text = "1"
    return tostring(root, encoding="unicode")


def build_inner_xml(
    corp_id: str,
    sender_id: str,
    group_id: str,
    content: str,
) -> str:
    root = Element("xml")
    SubElement(root, "ToUserName").text = corp_id
    SubElement(root, "FromUserName").text = sender_id
    SubElement(root, "CreateTime").text = str(int(time.time()))
    SubElement(root, "MsgType").text = "text"
    SubElement(root, "Content").text = content
    SubElement(root, "MsgId").text = f"debug-{uuid4().hex[:12]}"
    SubElement(root, "AgentID").text = "1"
    SubElement(root, "ChatId").text = group_id
    SubElement(root, "ChatName").text = "回调调试群"
    return tostring(root, encoding="unicode")


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug a WeCom callback locally.")
    parser.add_argument(
        "mode",
        choices=("roundtrip", "verify", "post"),
        help="Crypto roundtrip or HTTP callback verification/post.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="FastAPI base URL.",
    )
    parser.add_argument("--content", default="周六约饭")
    parser.add_argument("--group-id", default="debug-group-001")
    parser.add_argument("--sender-id", default="debug-user-001")
    args = parser.parse_args()

    try:
        crypto = get_wecom_crypto()
    except WeComCryptoError as exc:
        print(f"回调配置不完整：{exc}")
        return 1

    if args.mode == "roundtrip":
        encrypted = crypto.encrypt(args.content)
        decrypted = crypto.decrypt(encrypted)
        print(f"encrypted={encrypted}")
        print(f"decrypted={decrypted}")
        return 0 if decrypted == args.content else 1

    if args.mode == "verify":
        echostr = crypto.encrypt("callback-verified")
        timestamp = str(int(time.time()))
        nonce = uuid4().hex[:8]
        signature = crypto.signature(timestamp, nonce, echostr)
        response = httpx.get(
            f"{args.base_url.rstrip('/')}/wecom/callback",
            params={
                "msg_signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
                "echostr": echostr,
            },
            timeout=10.0,
        )
        print(f"status={response.status_code}")
        print(response.text)
        return 0 if response.status_code == 200 else 1

    inner_xml = build_inner_xml(
        corp_id=crypto.corp_id,
        sender_id=args.sender_id,
        group_id=args.group_id,
        content=args.content,
    )
    encrypted = crypto.encrypt(inner_xml)
    outer_xml = build_outer_xml(encrypted, crypto.corp_id)
    timestamp = str(int(time.time()))
    nonce = uuid4().hex[:8]
    signature = crypto.signature(timestamp, nonce, encrypted)
    response = httpx.post(
        f"{args.base_url.rstrip('/')}/wecom/callback",
        params={
            "msg_signature": signature,
            "timestamp": timestamp,
            "nonce": nonce,
        },
        content=outer_xml.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=10.0,
    )
    print(f"status={response.status_code}")
    print(response.text)
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
