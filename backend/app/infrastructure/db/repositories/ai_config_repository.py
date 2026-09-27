import base64
import hashlib
import os
from typing import Any, Dict
from cryptography.fernet import Fernet, InvalidToken
from backend.app.infrastructure.db.connection import transaction


def _get_fernet() -> Fernet:
    seed = os.environ.get("EASYEXAM_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if not seed or not seed.strip():
        raise RuntimeError("EASYEXAM_SECRET_KEY or SECRET_KEY environment variable is not configured; refusing to encrypt or decrypt sensitive credentials.")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.strip().encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(secret: str | None) -> str:
    if not secret:
        return ""
    if secret.startswith("enc:"):
        return secret
    fernet = _get_fernet()
    token = fernet.encrypt(secret.encode("utf-8")).decode("utf-8")
    return f"enc:{token}"


def decrypt_secret(secret: str | None) -> str:
    if not secret:
        return ""
    if not secret.startswith("enc:"):
        # Legacy plaintext compatibility: return as-is
        return secret
    fernet = _get_fernet()
    try:
        return fernet.decrypt(secret[4:].encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(f"Failed to decrypt sensitive secret: key mismatch or corrupted ciphertext ({exc})") from exc
    except Exception as exc:
        raise ValueError(f"Failed to decrypt sensitive secret: {exc}") from exc


def mask_secret(secret: str | None) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "********"
    return secret[:3] + "******" + secret[-4:]


class AiConfigRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_config(self, user_id: str, mask_secrets: bool = True) -> dict:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT ai_provider, ai_api_base, ai_model, ai_api_key,
                          search_provider, search_api_key, search_api_base, updated_at
                   FROM user_ai_configs
                   WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
            if not row:
                return {
                    "ai_provider": "openai",
                    "ai_api_base": "https://api.openai.com/v1",
                    "ai_model": "gpt-4o-mini",
                    "ai_api_key": "",
                    "search_provider": "open-webSearch",
                    "search_api_key": "",
                    "search_api_base": "http://localhost:8000/v1/search",
                    "is_configured": False,
                }
            data = dict(row)
            stored_ai_key = data.get("ai_api_key") or ""
            stored_search_key = data.get("search_api_key") or ""
            plain_ai_key = decrypt_secret(stored_ai_key)
            plain_search_key = decrypt_secret(stored_search_key)

            # Transparent on-the-fly upgrade of legacy plaintext to ciphertext in DB
            need_upgrade = (
                (stored_ai_key and not stored_ai_key.startswith("enc:")) or
                (stored_search_key and not stored_search_key.startswith("enc:"))
            )
            if need_upgrade:
                upgraded_ai = encrypt_secret(plain_ai_key) if plain_ai_key else ""
                upgraded_search = encrypt_secret(plain_search_key) if plain_search_key else ""
                conn.execute(
                    "UPDATE user_ai_configs SET ai_api_key = ?, search_api_key = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (upgraded_ai, upgraded_search, user_id),
                )

            data["is_configured"] = bool(plain_ai_key.strip() or "localhost" in data.get("ai_api_base", ""))
            if mask_secrets:
                data["ai_api_key"] = mask_secret(plain_ai_key)
                data["search_api_key"] = mask_secret(plain_search_key)
            else:
                data["ai_api_key"] = plain_ai_key
                data["search_api_key"] = plain_search_key
            return data

    def save_config(self, user_id: str, payload: Dict[str, Any]) -> dict:
        with transaction(self.db_path) as conn:
            existing = conn.execute(
                "SELECT ai_api_key, search_api_key FROM user_ai_configs WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            existing_ai_key_cipher = existing["ai_api_key"] if existing else ""
            existing_search_key_cipher = existing["search_api_key"] if existing else ""

            # Ensure existing legacy plaintext is upgraded to ciphertext if retained
            if existing_ai_key_cipher and not existing_ai_key_cipher.startswith("enc:"):
                existing_ai_key_cipher = encrypt_secret(existing_ai_key_cipher)
            if existing_search_key_cipher and not existing_search_key_cipher.startswith("enc:"):
                existing_search_key_cipher = encrypt_secret(existing_search_key_cipher)

            new_ai_key = payload.get("ai_api_key")
            if not new_ai_key or "******" in new_ai_key:
                ai_key_to_save = existing_ai_key_cipher
            else:
                ai_key_to_save = encrypt_secret(new_ai_key.strip())

            new_search_key = payload.get("search_api_key")
            if not new_search_key or "******" in new_search_key:
                search_key_to_save = existing_search_key_cipher
            else:
                search_key_to_save = encrypt_secret(new_search_key.strip())

            ai_provider = payload.get("ai_provider") or "openai"
            ai_api_base = payload.get("ai_api_base") or "https://api.openai.com/v1"
            ai_model = payload.get("ai_model") or "gpt-4o-mini"
            search_provider = payload.get("search_provider") or "open-webSearch"
            search_api_base = payload.get("search_api_base") or "http://localhost:8000/v1/search"

            conn.execute(
                """INSERT INTO user_ai_configs(
                    user_id, ai_provider, ai_api_base, ai_model, ai_api_key,
                    search_provider, search_api_key, search_api_base, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    ai_provider = excluded.ai_provider,
                    ai_api_base = excluded.ai_api_base,
                    ai_model = excluded.ai_model,
                    ai_api_key = excluded.ai_api_key,
                    search_provider = excluded.search_provider,
                    search_api_key = excluded.search_api_key,
                    search_api_base = excluded.search_api_base,
                    updated_at = CURRENT_TIMESTAMP""",
                (
                    user_id, ai_provider, ai_api_base, ai_model, ai_key_to_save,
                    search_provider, search_key_to_save, search_api_base,
                ),
            )
        return self.get_config(user_id, mask_secrets=True)
