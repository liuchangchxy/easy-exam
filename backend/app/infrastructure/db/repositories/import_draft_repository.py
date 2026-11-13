"""Resumable import wizard drafts.

The client owns the shape of ``state``; the server stores it opaquely so the
wizard can be extended without a schema migration. Drafts are disposable
scratch data, so deleting one is a hard delete.
"""
import json
import uuid
from typing import Any

from backend.app.infrastructure.db.connection import transaction

MAX_STATE_BYTES = 2 * 1024 * 1024
DRAFT_STATUSES = ("OPEN", "CONSUMED", "DISCARDED")


class DraftStateTooLargeError(ValueError):
    """Raised when the opaque wizard state exceeds the 2 MB storage budget."""


class ImportDraftRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _require_editor(conn, bank_id: str, user_id: str) -> str:
        row = conn.execute(
            "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
            (bank_id, user_id),
        ).fetchone()
        if not row:
            raise LookupError("bank not found")
        if row[0] not in ("ADMIN", "EDITOR"):
            raise PermissionError("member cannot import into this bank")
        return row[0]

    @staticmethod
    def _encode_state(state: Any) -> str:
        encoded = json.dumps(state if state is not None else {}, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > MAX_STATE_BYTES:
            raise DraftStateTooLargeError(f"draft state exceeds {MAX_STATE_BYTES} bytes")
        return encoded

    @staticmethod
    def _serialize(row, include_state: bool = True) -> dict:
        data = {
            "id": row["id"],
            "bank_id": row["bank_id"],
            "source_kind": row["source_kind"],
            "filename": row["filename"],
            "step": row["step"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_state:
            try:
                data["state"] = json.loads(row["state_json"] or "{}")
            except (TypeError, ValueError):
                data["state"] = {}
        return data

    # -------------------------------------------------------------------- CRUD

    def create(
        self,
        user_id: str,
        bank_id: str,
        source_kind: str = "file",
        filename: str | None = None,
        step: int = 1,
        state: Any = None,
    ) -> dict:
        encoded = self._encode_state(state)
        draft_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
            conn.execute(
                """INSERT INTO import_drafts(
                       id, user_id, bank_id, source_kind, filename, step, state_json, status
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
                (draft_id, user_id, bank_id, source_kind or "file", filename, int(step or 1), encoded),
            )
        return self.get(user_id, draft_id)

    def list_for_bank(self, user_id: str, bank_id: str, status: str = "OPEN") -> list[dict]:
        normalized = (status or "OPEN").strip().upper()
        if normalized not in DRAFT_STATUSES and normalized != "ALL":
            raise ValueError("status must be OPEN, CONSUMED, DISCARDED or ALL")
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
            sql = """SELECT id, bank_id, source_kind, filename, step, status, state_json,
                            created_at, updated_at
                     FROM import_drafts
                     WHERE user_id = ? AND bank_id = ?"""
            params: list = [user_id, bank_id]
            if normalized != "ALL":
                sql += " AND status = ?"
                params.append(normalized)
            sql += " ORDER BY created_at DESC, rowid DESC"
            rows = conn.execute(sql, params).fetchall()
        return [self._serialize(row, include_state=False) for row in rows]

    def get(self, user_id: str, draft_id: str) -> dict:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT id, bank_id, source_kind, filename, step, status, state_json,
                          created_at, updated_at
                   FROM import_drafts WHERE id = ? AND user_id = ?""",
                (draft_id, user_id),
            ).fetchone()
        if not row:
            # Someone else's draft must be indistinguishable from a missing one.
            raise LookupError("draft not found")
        return self._serialize(row, include_state=True)

    def update(self, user_id: str, draft_id: str, fields: dict) -> dict:
        assignments = []
        params: list = []
        if "state" in fields:
            assignments.append("state_json = ?")
            params.append(self._encode_state(fields["state"]))
        if "step" in fields:
            assignments.append("step = ?")
            params.append(int(fields["step"]))
        if "filename" in fields:
            assignments.append("filename = ?")
            params.append(fields["filename"])
        if "status" in fields:
            status = str(fields["status"] or "").strip().upper()
            if status not in DRAFT_STATUSES:
                raise ValueError("status must be OPEN, CONSUMED or DISCARDED")
            assignments.append("status = ?")
            params.append(status)
        if not assignments:
            return self.get(user_id, draft_id)

        assignments.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([draft_id, user_id])
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE import_drafts SET {', '.join(assignments)} WHERE id = ? AND user_id = ?",
                params,
            )
            if cursor.rowcount == 0:
                raise LookupError("draft not found")
        return self.get(user_id, draft_id)

    def delete(self, user_id: str, draft_id: str) -> None:
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM import_drafts WHERE id = ? AND user_id = ?",
                (draft_id, user_id),
            )
            if cursor.rowcount == 0:
                raise LookupError("draft not found")
