import base64
import hashlib
import hmac
import os
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from app.config import get_settings


class WeComCryptoError(ValueError):
    pass


class WeComCrypto:
    def __init__(self, token: str, encoding_aes_key: str, corp_id: str) -> None:
        if len(encoding_aes_key) != 43:
            raise WeComCryptoError("EncodingAESKey must contain 43 characters")

        self._token = token
        self._corp_id = corp_id
        self._aes_key = base64.b64decode(f"{encoding_aes_key}=")
        if len(self._aes_key) != 32:
            raise WeComCryptoError("EncodingAESKey must decode to 32 bytes")

    def signature(self, timestamp: str, nonce: str, encrypted: str) -> str:
        values = sorted([self._token, timestamp, nonce, encrypted])
        return hashlib.sha1("".join(values).encode("utf-8")).hexdigest()

    def verify_signature(
        self,
        signature: str,
        timestamp: str,
        nonce: str,
        encrypted: str,
    ) -> bool:
        expected = self.signature(timestamp, nonce, encrypted)
        return hmac.compare_digest(expected, signature)

    def decrypt(self, encrypted: str) -> str:
        try:
            ciphertext = base64.b64decode(encrypted)
            decryptor = Cipher(
                algorithms.AES(self._aes_key),
                modes.CBC(self._aes_key[:16]),
            ).decryptor()
            padded = decryptor.update(ciphertext) + decryptor.finalize()
            unpadder = PKCS7(128).unpadder()
            plain = unpadder.update(padded) + unpadder.finalize()
        except Exception as exc:
            raise WeComCryptoError("failed to decrypt callback payload") from exc

        if len(plain) < 20:
            raise WeComCryptoError("callback payload is too short")

        message_length = struct.unpack("!I", plain[16:20])[0]
        message = plain[20 : 20 + message_length]
        corp_id = plain[20 + message_length :].decode("utf-8")
        if corp_id != self._corp_id:
            raise WeComCryptoError("callback corp_id mismatch")
        return message.decode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        message = plaintext.encode("utf-8")
        payload = (
            os.urandom(16)
            + struct.pack("!I", len(message))
            + message
            + self._corp_id.encode("utf-8")
        )
        padder = PKCS7(128).padder()
        padded = padder.update(payload) + padder.finalize()
        encryptor = Cipher(
            algorithms.AES(self._aes_key),
            modes.CBC(self._aes_key[:16]),
        ).encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode("utf-8")


def get_wecom_crypto() -> WeComCrypto:
    settings = get_settings()
    if (
        not settings.wecom_callback_token
        or not settings.wecom_encoding_aes_key
        or not settings.wecom_corp_id
    ):
        raise WeComCryptoError("WeCom callback configuration is incomplete")
    return WeComCrypto(
        token=settings.wecom_callback_token,
        encoding_aes_key=settings.wecom_encoding_aes_key,
        corp_id=settings.wecom_corp_id,
    )
