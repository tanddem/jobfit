"""Unit tests for the SQLite schema reset."""

from app.db import connect, init_db


def tables(db_path):
    conn = connect(db_path)
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    conn.close()
    return {row["name"] for row in rows}


def test_creates_parent_directory_and_tables(tmp_path):
    db_path = tmp_path / "nested" / "jobfit.sqlite3"
    init_db(db_path)
    assert tables(db_path) == {"users", "uploads"}


def test_reinit_drops_existing_rows(tmp_path):
    db_path = tmp_path / "jobfit.sqlite3"
    init_db(db_path)
    conn = connect(db_path)
    with conn:
        conn.execute("INSERT INTO users (name) VALUES ('Linh')")
    conn.close()

    init_db(db_path)

    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    conn.close()
