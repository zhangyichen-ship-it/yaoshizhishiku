"""Encryption helpers for secrets persisted by the built-in AI module."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config.setting import settings as core_settings
from app.core.logger import logger


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(core_settings.SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        logger.warning("AI persisted secret could not be decrypted; falling back to environment configuration")
        return None
