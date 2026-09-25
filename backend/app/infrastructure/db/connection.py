"""SQLite connection and versioned migration runner for EasyExam v1."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Generator


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


MIGRATIONS = {
    1: """
    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE user_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_user_sessions_token ON user_sessions(token_hash);
    CREATE TABLE question_banks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '默认分类',
        is_deleted INTEGER NOT NULL DEFAULT 0,
        created_by TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE question_bank_members (
        bank_id TEXT NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK(role IN ('ADMIN', 'EDITOR', 'MEMBER')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(bank_id, user_id)
    );
    CREATE TABLE questions (
        id TEXT PRIMARY KEY,
        created_by TEXT NOT NULL REFERENCES users(id),
        is_deleted INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE question_versions (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        version_number INTEGER NOT NULL,
        type TEXT NOT NULL,
        stem TEXT NOT NULL,
        options_json TEXT NOT NULL DEFAULT '[]',
        answer TEXT NOT NULL DEFAULT '',
        explanation TEXT NOT NULL DEFAULT '',
        difficulty INTEGER NOT NULL DEFAULT 3,
        tags_json TEXT NOT NULL DEFAULT '[]',
        created_by TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(question_id, version_number)
    );
    CREATE TABLE bank_question_items (
        bank_id TEXT NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(bank_id, question_id)
    );
    CREATE INDEX idx_bank_question_items_question ON bank_question_items(question_id);
    """,
    2: """
    CREATE TABLE practice_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        bank_id TEXT NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
        mode TEXT NOT NULL,
        total_questions INTEGER NOT NULL DEFAULT 0,
        current_index INTEGER NOT NULL DEFAULT 0,
        time_spent INTEGER NOT NULL DEFAULT 0,
        time_limit INTEGER NOT NULL DEFAULT 0,
        is_completed INTEGER NOT NULL DEFAULT 0,
        score REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE answer_attempts (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        session_id TEXT NOT NULL REFERENCES practice_sessions(id) ON DELETE CASCADE,
        bank_id TEXT NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        question_version_id TEXT NOT NULL REFERENCES question_versions(id) ON DELETE RESTRICT,
        user_answer_json TEXT NOT NULL,
        score_ratio REAL NOT NULL DEFAULT 0,
        correctness TEXT NOT NULL,
        mastery_status TEXT NOT NULL,
        time_spent INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_attempts_user_question ON answer_attempts(user_id, question_id);
    CREATE TABLE learning_records (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        mistake_count INTEGER NOT NULL DEFAULT 0,
        consecutive_correct INTEGER NOT NULL DEFAULT 0,
        mastery_status TEXT NOT NULL DEFAULT 'UNSEEN',
        is_cleared INTEGER NOT NULL DEFAULT 0,
        last_attempt_at TEXT,
        PRIMARY KEY(user_id, question_id)
    );
    CREATE TABLE fsrs_cards (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        state INTEGER NOT NULL DEFAULT 0,
        stability REAL NOT NULL DEFAULT 0,
        difficulty REAL NOT NULL DEFAULT 5,
        due_at TEXT,
        PRIMARY KEY(user_id, question_id)
    );
    CREATE TABLE kill_records (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        killed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, question_id)
    );
    CREATE TABLE learning_events (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        aggregate_type TEXT NOT NULL,
        aggregate_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    3: """
    CREATE TABLE explanation_versions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        question_version_id TEXT NOT NULL REFERENCES question_versions(id) ON DELETE RESTRICT,
        source TEXT NOT NULL CHECK(source IN ('OFFICIAL', 'AI', 'WEB', 'PERSONAL')),
        content TEXT NOT NULL,
        provider TEXT,
        is_candidate INTEGER NOT NULL DEFAULT 1,
        is_adopted INTEGER NOT NULL DEFAULT 0,
        parent_version_id TEXT REFERENCES explanation_versions(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_explanation_question ON explanation_versions(user_id, question_id, created_at);
    CREATE TABLE explanation_evidence (
        id TEXT PRIMARY KEY,
        explanation_id TEXT NOT NULL REFERENCES explanation_versions(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        url TEXT,
        summary TEXT,
        retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    4: """
    ALTER TABLE practice_sessions ADD COLUMN answers_json TEXT NOT NULL DEFAULT '{}';
    ALTER TABLE practice_sessions ADD COLUMN flags_json TEXT NOT NULL DEFAULT '[]';
    ALTER TABLE practice_sessions ADD COLUMN questions_json TEXT NOT NULL DEFAULT '[]';
    """,
    5: """
    CREATE TABLE exam_profiles (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE exam_blueprints (
        id TEXT PRIMARY KEY,
        profile_id TEXT NOT NULL REFERENCES exam_profiles(id) ON DELETE CASCADE,
        version_number INTEGER NOT NULL DEFAULT 1,
        blueprint_json TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(profile_id, version_number)
    );
    CREATE TABLE chapters (
        id TEXT PRIMARY KEY,
        bank_id TEXT NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
        parent_id TEXT REFERENCES chapters(id),
        name TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE knowledge_tags (
        id TEXT PRIMARY KEY,
        bank_id TEXT NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        UNIQUE(bank_id, name)
    );
    """,
    6: """
    CREATE TABLE personal_assets (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_id TEXT REFERENCES questions(id) ON DELETE CASCADE,
        knowledge_tag_id TEXT REFERENCES knowledge_tags(id) ON DELETE CASCADE,
        asset_type TEXT NOT NULL CHECK(asset_type IN ('NOTE', 'SUMMARY', 'MNEMONIC')),
        content TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE import_jobs (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        bank_id TEXT REFERENCES question_banks(id) ON DELETE SET NULL,
        filename TEXT,
        format TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('PENDING', 'PRECHECK_FAILED', 'IMPORTED', 'FAILED')),
        reason TEXT,
        imported_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
    );
    """,
    7: """
    CREATE TABLE mistake_records (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        bank_id TEXT REFERENCES question_banks(id) ON DELETE SET NULL,
        mistake_count INTEGER NOT NULL DEFAULT 0,
        consecutive_correct INTEGER NOT NULL DEFAULT 0,
        is_cleared INTEGER NOT NULL DEFAULT 0,
        last_review_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, question_id)
    );
    CREATE INDEX idx_mistake_records_user_bank ON mistake_records(user_id, bank_id, is_cleared);
    """,
    8: """
    ALTER TABLE practice_sessions ADD COLUMN exam_profile_id TEXT REFERENCES exam_profiles(id) ON DELETE SET NULL;
    ALTER TABLE practice_sessions ADD COLUMN blueprint_id TEXT REFERENCES exam_blueprints(id) ON DELETE SET NULL;
    """,
    9: """
    ALTER TABLE fsrs_cards ADD COLUMN last_review_at TEXT;
    ALTER TABLE answer_attempts ADD COLUMN fsrs_rating INTEGER CHECK(fsrs_rating BETWEEN 1 AND 4);
    ALTER TABLE answer_attempts ADD COLUMN mistake_cause TEXT;
    ALTER TABLE mistake_records ADD COLUMN mistake_cause TEXT;
    """,
    10: """
    CREATE TABLE weak_question_flags (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, question_id)
    );
    """,
    11: """
    ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0;
    """,
    12: """
    ALTER TABLE answer_attempts ADD COLUMN card_snapshot_json TEXT;
    """,
    13: """
    -- Adapted from MiaowTest (commit 803dadc, MIT License)
    CREATE TABLE ai_conversations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
        question_version_id TEXT NOT NULL REFERENCES question_versions(id) ON DELETE RESTRICT,
        title TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_ai_conversations_user_qv ON ai_conversations(user_id, question_version_id);
    CREATE TABLE ai_messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
        content TEXT NOT NULL,
        parent_message_id TEXT REFERENCES ai_messages(id) ON DELETE SET NULL,
        message_status TEXT NOT NULL DEFAULT 'success' CHECK(message_status IN ('sending', 'success', 'error')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(conversation_id, sequence)
    );
    CREATE INDEX idx_ai_messages_conv_seq ON ai_messages(conversation_id, sequence);
    """,
    14: """
    -- Multi-device concurrent conflict tracking (SPEC §2.1)
    CREATE TABLE question_conflicts (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        base_version_number INTEGER NOT NULL,
        server_version_number INTEGER NOT NULL,
        client_version_number INTEGER NOT NULL,
        is_resolved INTEGER NOT NULL DEFAULT 0,
        resolved_version_number INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        resolved_at TEXT
    );
    CREATE INDEX idx_question_conflicts_unresolved ON question_conflicts(question_id, is_resolved);
    """,
}



def migrate(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(str(path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for version in sorted(MIGRATIONS):
            if version in applied:
                continue
            with conn:
                conn.executescript(MIGRATIONS[version])
                conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
    finally:
        conn.close()


@contextmanager
def transaction(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
