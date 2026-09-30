from xml.etree import ElementTree

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.clients.wecom_crypto import WeComCryptoError, get_wecom_crypto
from app.db import get_db
from app.services.processing import process_inbound_message
from app.services.wecom_callback import (
    WeComCallbackMessageError,
    parse_callback_message,
)

router = APIRouter(prefix="/wecom", tags=["wecom"])


@router.get("/callback", response_class=PlainTextResponse)
def verify_wecom_callback(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
) -> str:
    try:
        crypto = get_wecom_crypto()
        if not crypto.verify_signature(
            msg_signature,
            timestamp,
            nonce,
            echostr,
        ):
            raise HTTPException(status_code=403, detail="invalid callback signature")
        return crypto.decrypt(echostr)
    except WeComCryptoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/callback", response_class=PlainTextResponse)
async def receive_wecom_callback(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    db: Session = Depends(get_db),
) -> str:
    body = (await request.body()).decode("utf-8")
    try:
        encrypted = ElementTree.fromstring(body).findtext("Encrypt")
    except ElementTree.ParseError as exc:
        raise HTTPException(status_code=400, detail="invalid callback XML") from exc

    if not encrypted:
        raise HTTPException(status_code=400, detail="missing Encrypt field")

    try:
        crypto = get_wecom_crypto()
        if not crypto.verify_signature(
            msg_signature,
            timestamp,
            nonce,
            encrypted,
        ):
            raise HTTPException(status_code=403, detail="invalid callback signature")
        plaintext = crypto.decrypt(encrypted)
        payload = parse_callback_message(plaintext)
    except WeComCryptoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WeComCallbackMessageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    process_inbound_message(db, payload)
    return "success"
