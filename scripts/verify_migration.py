"""Validate structural counts in a migrated v1 database."""
import argparse
import json
import sqlite3


def verify_migration(target: str, source_counts: dict) -> dict:
    conn = sqlite3.connect(target)
    try:
        result = {
            "banks": conn.execute("SELECT COUNT(*) FROM question_banks").fetchone()[0],
            "questions": conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
            "question_versions": conn.execute("SELECT COUNT(*) FROM question_versions").fetchone()[0],
            "bank_question_items": conn.execute("SELECT COUNT(*) FROM bank_question_items").fetchone()[0],
            "practice_sessions": conn.execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0],
            "answer_attempts": conn.execute("SELECT COUNT(*) FROM answer_attempts").fetchone()[0],
            "learning_records": conn.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0],
            "mistake_records": conn.execute("SELECT COUNT(*) FROM mistake_records").fetchone()[0],
            "foreign_key_errors": conn.execute("PRAGMA foreign_key_check").fetchall(),
        }
        errors = []
        expected_banks = source_counts.get("banks")
        expected_questions = source_counts.get("questions")
        expected_sessions = source_counts.get("sessions", source_counts.get("practice_sessions"))
        expected_mistakes = source_counts.get("mistake_records")

        if expected_banks is not None and result["banks"] != expected_banks:
            errors.append(f"banks: expected {expected_banks}, got {result['banks']}")
        if expected_questions is not None and result["questions"] != expected_questions:
            errors.append(f"questions: expected {expected_questions}, got {result['questions']}")
        if expected_sessions is not None and result["practice_sessions"] != expected_sessions:
            errors.append(f"practice_sessions: expected {expected_sessions}, got {result['practice_sessions']}")
        if expected_mistakes is not None and result["mistake_records"] != expected_mistakes:
            errors.append(f"mistake_records: expected {expected_mistakes}, got {result['mistake_records']}")

        if errors:
            raise ValueError(f"migrated counts do not match source: {', '.join(errors)}")
        if result["foreign_key_errors"]:
            raise ValueError(f"foreign key errors: {result['foreign_key_errors']}")
        return result
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--source-counts", required=True)
    args = parser.parse_args()
    print(json.dumps(verify_migration(args.target, json.loads(args.source_counts)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
