import time

from app.clients.wecom_crypto import WeComCrypto

TOKEN = "test-token"
AES_KEY = "A" * 43
CORP_ID = "test-corp"


def _crypto() -> WeComCrypto:
    return WeComCrypto(
        token=TOKEN,
        encoding_aes_key=AES_KEY,
        corp_id=CORP_ID,
    )


def _callback_query(encrypted: str) -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = "test-nonce"
    crypto = _crypto()
    return {
        "msg_signature": crypto.signature(timestamp, nonce, encrypted),
        "timestamp": timestamp,
        "nonce": nonce,
    }


def test_wecom_crypto_round_trip() -> None:
    crypto = _crypto()
    plaintext = "<xml><Content>hello</Content></xml>"

    encrypted = crypto.encrypt(plaintext)

    assert crypto.decrypt(encrypted) == plaintext


def test_wecom_callback_verification_returns_plaintext(client) -> None:
    plaintext = "callback-verified"
    encrypted = _crypto().encrypt(plaintext)
    query = _callback_query(encrypted)

    response = client.get(
        "/wecom/callback",
        params={**query, "echostr": encrypted},
    )

    assert response.status_code == 200
    assert response.text == plaintext


def test_wecom_callback_message_creates_activity(client) -> None:
    timestamp = str(int(time.time()))
    nonce = "callback-nonce"
    inner_xml = (
        "<xml>"
        "<ToUserName><![CDATA[test-corp]]></ToUserName>"
        "<FromUserName><![CDATA[callback-user-001]]></FromUserName>"
        f"<CreateTime>{timestamp}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        "<Content><![CDATA[周六约饭]]></Content>"
        "<MsgId>callback-msg-001</MsgId>"
        "<AgentID>1</AgentID>"
        "<ChatId><![CDATA[callback-group-001]]></ChatId>"
        "<ChatName><![CDATA[回调测试群]]></ChatName>"
        "</xml>"
    )
    crypto = _crypto()
    encrypted = crypto.encrypt(inner_xml)
    outer_xml = (
        "<xml>"
        "<ToUserName><![CDATA[test-corp]]></ToUserName>"
        f"<Encrypt><![CDATA[{encrypted}]]></Encrypt>"
        "<AgentID>1</AgentID>"
        "</xml>"
    )
    signature = crypto.signature(timestamp, nonce, encrypted)

    response = client.post(
        "/wecom/callback",
        params={
            "msg_signature": signature,
            "timestamp": timestamp,
            "nonce": nonce,
        },
        content=outer_xml,
        headers={"Content-Type": "application/xml"},
    )

    assert response.status_code == 200
    assert response.text == "success"

    activities = client.get(
        "/admin/activities",
        params={"group_id": "callback-group-001"},
    ).json()
    assert len(activities) == 1
    assert activities[0]["initiator_id"] == "callback-user-001"
