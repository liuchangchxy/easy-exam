import uuid

from backend.app.infrastructure.db.connection import transaction


JOB_PUBLIC_FIELDS = (
    "id",
    "bank_id",
    "filename",
    "format",
    "status",
    "progress",
    "total",
    "imported_count",
    "reason",
    "created_at",
    "completed_at",
)


class ImportJobRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create(self, user_id: str, bank_id: str, fmt: str, filename: str | None = None) -> dict:
        job_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute(
                "INSERT INTO import_jobs(id, user_id, bank_id, filename, format, status) VALUES (?, ?, ?, ?, ?, 'PENDING')",
                (job_id, user_id, bank_id, filename, fmt),
            )
        return self.get(job_id, user_id)

    def create_async(self, user_id: str, bank_id: str, fmt: str, filename: str | None = None) -> dict:
        """Create a job already RUNNING: the caller starts its worker immediately."""
        job_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute(
                """INSERT INTO import_jobs(id, user_id, bank_id, filename, format, status)
                   VALUES (?, ?, ?, ?, ?, 'RUNNING')""",
                (job_id, user_id, bank_id, filename, fmt),
            )
        return self.get(job_id, user_id)

    def finish(self, job_id: str, user_id: str, status: str, imported_count: int = 0, reason: str | None = None) -> dict | None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE import_jobs SET status = ?, imported_count = ?, reason = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (status, imported_count, reason, job_id, user_id),
            )
        return self.get(job_id, user_id)

    def set_total(self, job_id: str, total: int) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE import_jobs SET total = ? WHERE id = ? AND status = 'RUNNING'",
                (int(total), job_id),
            )

    def is_cancel_requested(self, job_id: str) -> bool:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT cancel_requested FROM import_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return bool(row and row[0])

    def request_cancel(self, job_id: str) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE import_jobs SET cancel_requested = 1 WHERE id = ? AND status IN ('PENDING', 'RUNNING')",
                (job_id,),
            )

    def finish_async(
        self,
        job_id: str,
        status: str,
        imported_count: int,
        reason: str | None = None,
        progress: int | None = None,
        total: int | None = None,
    ) -> dict | None:
        """Finalize a worker job. Never overwrites an already-final status."""
        with transaction(self.db_path) as conn:
            conn.execute(
                """UPDATE import_jobs
                   SET status = ?,
                       imported_count = ?,
                       reason = ?,
                       progress = COALESCE(?, progress),
                       total = COALESCE(?, total),
                       completed_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND status = 'RUNNING'""",
                (status, imported_count, reason, progress, total, job_id),
            )
        return self.get_any(job_id)

    def get(self, job_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT * FROM import_jobs WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()
            return dict(row) if row else None

    def get_any(self, job_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT * FROM import_jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def public_view(job: dict) -> dict:
        return {field: job.get(field) for field in JOB_PUBLIC_FIELDS}

    def list_for_bank(self, bank_id: str, user_id: str, limit: int = 50) -> list[dict]:
        with transaction(self.db_path) as conn:
            member = conn.execute(
                "SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
                (bank_id, user_id),
            ).fetchone()
            if not member:
                raise PermissionError("access denied")
            if not conn.execute("SELECT 1 FROM question_banks WHERE id = ?", (bank_id,)).fetchone():
                raise LookupError("bank not found")
            safe_limit = max(1, min(int(limit or 50), 200))
            rows = conn.execute(
                """SELECT id, user_id, bank_id, filename, format, status, reason,
                          imported_count, progress, total, created_at, completed_at
                   FROM import_jobs WHERE bank_id = ?
                   ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (bank_id, safe_limit),
            ).fetchall()
            return [dict(row) for row in rows]
