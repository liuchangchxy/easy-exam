import uuid

from backend.app.infrastructure.db.connection import transaction


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

    def finish(self, job_id: str, user_id: str, status: str, imported_count: int = 0, reason: str | None = None) -> dict | None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE import_jobs SET status = ?, imported_count = ?, reason = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (status, imported_count, reason, job_id, user_id),
            )
        return self.get(job_id, user_id)

    def get(self, job_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT * FROM import_jobs WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()
            return dict(row) if row else None
