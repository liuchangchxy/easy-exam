"""Opaque bearer session token utilities."""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expires_at(hours: int = 24 * 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
