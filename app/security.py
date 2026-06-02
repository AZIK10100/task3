import base64
import hmac
import hashlib
import logging
import os
import re

from django.conf import settings
from django.db import connection


CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
OTP_RE = re.compile(r"(?i)\b(otp|code|verification_code|password)\b([:=\s]+)(\d{4,8})\b")


def generate_hash(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_hash(payload: str, secret: str, signature: str) -> bool:
    expected = generate_hash(payload, secret)
    return hmac.compare_digest(expected, signature or "")


def get_user_secret(user) -> str:
    secret = getattr(user, "secret", None)
    if secret:
        return secret

    table_name = user._meta.db_table
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }
        if "secret" not in columns:
            return ""
        cursor.execute(f"SELECT secret FROM {table_name} WHERE id = %s", [user.pk])
        row = cursor.fetchone()
    return row[0] if row and row[0] else ""


def _get_encryption_key() -> bytes:
    key = os.getenv("ENCRYPTION_KEY", getattr(settings, "ENCRYPTION_KEY", ""))
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is required")
    return key.encode()


def get_cipher():
    from cryptography.fernet import Fernet

    return Fernet(_get_encryption_key())


def encrypt_card(card: str) -> str:
    if not card:
        return card
    return get_cipher().encrypt(str(card).encode()).decode()


def decrypt_card(encrypted_card: str) -> str:
    if not encrypted_card:
        return encrypted_card
    return get_cipher().decrypt(str(encrypted_card).encode()).decode()


def is_fernet_token(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    try:
        decoded = base64.urlsafe_b64decode(value.encode())
    except Exception:
        return False
    return decoded.startswith(b"\x80")


def mask_card(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 13:
        return value
    return f"{digits[:6]}******{digits[-4:]}"


def mask_sensitive_data(message: str) -> str:
    message = str(message)
    message = CARD_RE.sub(lambda match: mask_card(match.group(0)), message)
    message = OTP_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}*****", message)
    return message


class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        record.msg = mask_sensitive_data(record.getMessage())
        record.args = ()
        return True
