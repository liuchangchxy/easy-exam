"""One-time, auditable migration from the prototype SQLite schema to v1."""
import argparse
import json
import secrets
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict

from backend.app.infrastructure.db.connection import migrate, transaction
from backend.app.infrastructure.security.password import hash_password


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _source_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    return {name: _count(conn, name) for name in ("banks", "questions", "sessions", "mistake_records")}


def migrate_legacy_db(source: str, target: str, report_path: str, dry_run: bool = False) -> dict:
    source_path = Path(source)
    target_path = Path(target)
    report_file = Path(report_path)
    if not source_path.exists():
        raise FileNotFoundError(source)
    source_uri = f"file:{source_path.resolve().as_posix()}?mode=ro"
    source_conn = sqlite3.connect(source_uri, uri=True)
    source_conn.row_factory = sqlite3.Row
    try:
        source_counts = _source_counts(source_conn)
        result: Dict[str, Any] = {
            "source": str(source_path),
            "target": str(target_path),
            "dry_run": dry_run,
            "source_counts": source_counts,
            "counts": {"banks": source_counts["banks"], "questions": source_counts["questions"]},
            "unconverted": {
                "questions": [],
                "sessions": [],
                "answers": [],
                "mistakes": [],
            },
            "warnings": [],
            "backup_path": None,
        }
        if dry_run:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result

        if target_path.exists():
            raise FileExistsError(f"target already exists: {target_path}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = target_path.with_suffix(target_path.suffix + ".legacy-backup")
        shutil.copy2(source_path, backup_path)
        result["backup_path"] = str(backup_path)
        migrate(str(target_path))

        with transaction(str(target_path)) as target_conn:
            user_id = str(uuid.uuid4())
            temp_password = secrets.token_urlsafe(16)
            target_conn.execute(
                "INSERT INTO users(id, username, password_hash, must_change_password) VALUES (?, 'migrated-user', ?, 1)",
                (user_id, hash_password(temp_password)),
            )
            result["migrated_user"] = {
                "username": "migrated-user",
                "temporary_password": temp_password,
                "must_change_password": True,
            }
            bank_ids: Dict[str, str] = {}
            for row in source_conn.execute("SELECT id, name, description, category, created_at, updated_at FROM banks"):
                new_id = str(uuid.uuid4())
                bank_ids[str(row["id"])] = new_id
                target_conn.execute(
                    "INSERT INTO question_banks(id, name, description, category, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))",
                    (new_id, row["name"], row["description"] or "", row["category"] or "默认分类", user_id, row["created_at"], row["updated_at"]),
                )
                target_conn.execute("INSERT INTO question_bank_members(bank_id, user_id, role) VALUES (?, ?, 'ADMIN')", (new_id, user_id))

            for row in source_conn.execute("SELECT id, bank_id, type, stem, options_json, answer, explanation, difficulty, tags_json, created_at FROM questions"):
                question_id = str(row["id"])
                old_bank = str(row["bank_id"])
                if old_bank not in bank_ids:
                    result["unconverted"]["questions"].append({
                        "question_id": question_id,
                        "bank_id": old_bank,
                        "reason": f"bank_id {old_bank} not found in migrated question banks",
                    })
                    result["warnings"].append(f"Question {question_id} skipped: bank {old_bank} not found")
                    continue
                version_id = str(uuid.uuid4())
                target_conn.execute("INSERT INTO questions(id, created_by, created_at, updated_at) VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))", (question_id, user_id, row["created_at"], row["created_at"]))
                target_conn.execute(
                    """INSERT INTO question_versions(id, question_id, version_number, type, stem, options_json, answer, explanation, difficulty, tags_json, created_by, created_at)
                       VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))""",
                    (version_id, question_id, row["type"], row["stem"], row["options_json"] or "[]", row["answer"] or "", row["explanation"] or "", row["difficulty"] or 3, row["tags_json"] or "[]", user_id, row["created_at"]),
                )
                target_conn.execute("INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)", (bank_ids[old_bank], question_id))

            question_versions = {
                str(row["question_id"]): str(row["id"])
                for row in target_conn.execute("SELECT id, question_id FROM question_versions")
            }
            migrated_attempts = 0
            for row in source_conn.execute("SELECT * FROM sessions"):
                old_bank = str(row["bank_id"])
                if old_bank not in bank_ids:
                    result["unconverted"]["sessions"].append({
                        "session_id": str(row["id"]),
                        "bank_id": old_bank,
                        "reason": f"bank_id {old_bank} not found",
                    })
                    result["warnings"].append(f"Session {row['id']} skipped: bank {old_bank} not found")
                    continue
                target_conn.execute(
                    """INSERT INTO practice_sessions(
                        id, user_id, bank_id, mode, total_questions, current_index,
                        time_spent, time_limit, is_completed, score, answers_json,
                        flags_json, questions_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))""",
                    (
                        str(row["id"]), user_id, bank_ids[old_bank], row["mode"], row["total_questions"] or 0,
                        row["current_index"] or 0, row["time_spent"] or 0, row["time_limit"] or 0,
                        row["is_completed"] or 0, row["score"] or 0, row["answers_json"] or "{}",
                        row["flags_json"] or "[]", row["questions_json"] or "[]", row["created_at"], row["updated_at"],
                    ),
                )
                answers = json.loads(row["answers_json"] or "{}")
                for question_id, answer in answers.items():
                    if question_id not in question_versions or not isinstance(answer, dict):
                        result["unconverted"]["answers"].append({
                            "session_id": str(row["id"]),
                            "question_id": question_id,
                            "reason": "question_id not found in target question versions or answer payload not dict",
                        })
                        result["warnings"].append(f"Attempt in session {row['id']} for question {question_id} skipped: question not found")
                        continue
                    target_conn.execute(
                        """INSERT INTO answer_attempts(
                            id, user_id, session_id, bank_id, question_id, question_version_id,
                            user_answer_json, score_ratio, correctness, mastery_status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))""",
                        (
                            str(uuid.uuid4()), user_id, str(row["id"]), bank_ids[old_bank], question_id,
                            question_versions[question_id], json.dumps(answer.get("user_answer", answer.get("answer")), ensure_ascii=False),
                            float(answer.get("score_ratio", 0.0)),
                            "CORRECT" if answer.get("is_correct") else "INCORRECT",
                            "MASTERED" if answer.get("is_correct") else "WEAK", row["updated_at"],
                        ),
                    )
                    migrated_attempts += 1

            migrated_mistakes = 0
            for row in source_conn.execute("SELECT * FROM mistake_records"):
                old_question = str(row["question_id"])
                old_bank = str(row["bank_id"])
                if old_question not in question_versions or old_bank not in bank_ids:
                    result["unconverted"]["mistakes"].append({
                        "question_id": old_question,
                        "bank_id": old_bank,
                        "reason": "question or bank not found",
                    })
                    result["warnings"].append(f"Mistake record for question {old_question} in bank {old_bank} skipped: question or bank not found")
                    continue
                target_conn.execute(
                    """INSERT INTO learning_records(
                        user_id, question_id, mistake_count, consecutive_correct,
                        mastery_status, is_cleared, last_attempt_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id, old_question, row["mistake_count"] or 0, row["consecutive_correct"] or 0,
                        "MASTERED" if row["is_cleared"] else "WEAK", row["is_cleared"] or 0,
                        row["last_review_at"],
                    ),
                )
                target_conn.execute(
                    """INSERT INTO mistake_records(
                        user_id, question_id, bank_id, mistake_count,
                        consecutive_correct, is_cleared, last_review_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id, old_question, bank_ids[old_bank], row["mistake_count"] or 0,
                        row["consecutive_correct"] or 0, row["is_cleared"] or 0,
                        row["last_review_at"],
                    ),
                )
                target_conn.execute(
                    "INSERT INTO fsrs_cards(user_id, question_id, state, stability, difficulty, due_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, old_question, row["fsrs_state"] or 0, row["fsrs_stability"] or 0.0, row["fsrs_difficulty"] or 5.0, row["fsrs_due"]),
                )
                migrated_mistakes += 1

            fk_errors = target_conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_errors:
                raise ValueError(f"foreign key errors in migrated target: {fk_errors}")

            result["migrated"] = {"attempts": migrated_attempts, "mistakes": migrated_mistakes}
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    finally:
        source_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate_legacy_db(args.source, args.target, args.report, args.dry_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
