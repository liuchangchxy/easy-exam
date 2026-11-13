from typing import Optional

from backend.app.infrastructure.db.connection import transaction

ALLOW_REGISTRATION_KEY = "allow_registration"


class InstanceSettingsRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get(self, key: str, default: str = "") -> str:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM instance_settings WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "INSERT INTO instance_settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    def allow_registration(self) -> bool:
        raw = self.get(ALLOW_REGISTRATION_KEY, "true")
        return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}
