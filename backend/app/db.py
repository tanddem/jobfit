"""SQLite schema and connections.

Data survives restarts. The schema version lives in PRAGMA user_version. A
database from before accounts existed (a users table with no email column)
held only fake name-only users, so it is reset once on boot. Later changes
are additive and keyed on what is actually in the database, so a crash part
way through is safe to re-run.
"""

import sqlite3

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
    key TEXT PRIMARY KEY,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company TEXT NOT NULL,
    role_title TEXT NOT NULL,
    filename TEXT NOT NULL,
    cv_text TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    score_key TEXT NOT NULL REFERENCES scores(key),
    jd_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS uploads_by_application ON uploads (user_id, company, role_title);
"""

PRE_ACCOUNT_TABLES = ("uploads", "scores", "users")


def connect(db_path):
    """Open a connection with dict-like rows and foreign keys enforced.

    FastAPI may open, use and close one request's connection on different
    threadpool workers, so the same-thread check is off. Each connection still
    serves a single request.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    """Create the database if needed and bring its schema up to SCHEMA_VERSION."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if user_columns and "email" not in user_columns:
            conn.executescript("".join(f"DROP TABLE IF EXISTS {t};" for t in PRE_ACCOUNT_TABLES))
        conn.executescript(SCHEMA)
        upload_columns = {row["name"] for row in conn.execute("PRAGMA table_info(uploads)")}
        if "jd_url" not in upload_columns:
            conn.execute("ALTER TABLE uploads ADD COLUMN jd_url TEXT")
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    finally:
        conn.close()
