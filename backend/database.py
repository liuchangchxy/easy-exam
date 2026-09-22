"""Database connection and initialization module with SQLite WAL configuration."""
import os
import sqlite3
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    """Returns a SQLite connection configured with WAL mode and busy timeout."""
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str) -> None:
    """Initializes SQLite schema, executes table creation, and configures WAL."""
    db_file = Path(db_path)
    if db_file.parent and not db_file.parent.exists():
        db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS banks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT '默认分类',
                    question_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    bank_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    stem TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    explanation TEXT DEFAULT '',
                    difficulty INTEGER DEFAULT 3,
                    tags_json TEXT DEFAULT '[]',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(bank_id) REFERENCES banks(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_questions_bank_id ON questions(bank_id);

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    bank_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    total_questions INTEGER NOT NULL,
                    current_index INTEGER DEFAULT 0,
                    answers_json TEXT DEFAULT '{}',
                    flags_json TEXT DEFAULT '[]',
                    time_spent INTEGER DEFAULT 0,
                    time_limit INTEGER DEFAULT 0,
                    is_completed BOOLEAN DEFAULT 0,
                    score REAL DEFAULT 0.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(bank_id) REFERENCES banks(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_bank_id ON sessions(bank_id);

                CREATE TABLE IF NOT EXISTS mistake_records (
                    id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL UNIQUE,
                    bank_id TEXT NOT NULL,
                    mistake_count INTEGER DEFAULT 1,
                    consecutive_correct INTEGER DEFAULT 0,
                    is_cleared BOOLEAN DEFAULT 0,
                    mistake_cause TEXT,
                    fsrs_state INTEGER DEFAULT 0,
                    fsrs_stability REAL DEFAULT 0.0,
                    fsrs_difficulty REAL DEFAULT 5.0,
                    fsrs_due DATETIME,
                    last_review_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_mistakes_bank_id ON mistake_records(bank_id);
                CREATE INDEX IF NOT EXISTS idx_mistakes_cleared ON mistake_records(is_cleared);
                """
            )
    finally:
        conn.close()
