"""Unit tests for schema creation, versioning and the one-time pre-account reset."""

import sqlite3

from app.db import SCHEMA_VERSION, connect, init_db


def tables(db_path):
    conn = connect(db_path)
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    conn.close()
    return {row["name"] for row in rows}


def user_version(db_path):
    conn = connect(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    return version


def test_creates_parent_directory_tables_and_version(tmp_path):
    db_path = tmp_path / "nested" / "jobfit.sqlite3"
    init_db(db_path)
    assert tables(db_path) == {"users", "sessions", "scores", "uploads"}
    assert user_version(db_path) == SCHEMA_VERSION


def test_current_database_without_version_is_not_wiped(tmp_path):
    """A crash between creating tables and writing user_version must not lose accounts."""
    db_path = tmp_path / "jobfit.sqlite3"
    init_db(db_path)
    conn = connect(db_path)
    with conn:
        conn.execute("INSERT INTO users (email, name, password_hash) VALUES ('a@b.co', 'A', 'h')")
    conn.execute("PRAGMA user_version = 0")
    conn.close()

    init_db(db_path)

    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    conn.close()


def test_data_survives_restart(tmp_path):
    db_path = tmp_path / "jobfit.sqlite3"
    init_db(db_path)
    conn = connect(db_path)
    with conn:
        conn.execute("INSERT INTO users (email, name, password_hash) VALUES ('a@b.co', 'A', 'h')")
    conn.close()

    init_db(db_path)

    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    conn.close()


def test_pre_account_database_is_reset_once(tmp_path):
    db_path = tmp_path / "jobfit.sqlite3"
    old = sqlite3.connect(db_path)
    old.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE scores (key TEXT PRIMARY KEY, result_json TEXT NOT NULL);
        CREATE TABLE uploads (id INTEGER PRIMARY KEY, user_id INTEGER, filename TEXT,
                              cv_text TEXT, jd_text TEXT, score_key TEXT);
        INSERT INTO users (name) VALUES ('Linh');
        """
    )
    old.close()

    init_db(db_path)

    conn = connect(db_path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    assert {"email", "password_hash"} <= columns
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    conn.close()
    assert user_version(db_path) == SCHEMA_VERSION


def test_version_1_database_gains_jd_url_and_keeps_rows(tmp_path):
    db_path = tmp_path / "jobfit.sqlite3"
    init_db(db_path)
    conn = connect(db_path)
    with conn:
        conn.execute("ALTER TABLE uploads DROP COLUMN jd_url")
        conn.execute("INSERT INTO users (email, name, password_hash) VALUES ('a@b.co', 'A', 'h')")
        conn.execute("INSERT INTO scores (key, result_json) VALUES ('k', '{}')")
        conn.execute(
            "INSERT INTO uploads (user_id, company, role_title, filename, cv_text, jd_text, score_key) "
            "VALUES (1, 'Co', 'Role', 'cv.pdf', 'cv', 'jd', 'k')"
        )
    conn.execute("PRAGMA user_version = 1")
    conn.close()

    init_db(db_path)
    init_db(db_path)

    conn = connect(db_path)
    row = conn.execute("SELECT company, jd_url FROM uploads").fetchone()
    conn.close()
    assert (row["company"], row["jd_url"]) == ("Co", None)
    assert user_version(db_path) == SCHEMA_VERSION == 2
