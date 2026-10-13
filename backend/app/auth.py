"""Accounts: password hashing, server-side sessions, and the current-user dependency."""

import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, Request

from app.db import connect

COOKIE_NAME = "jobfit_session"
SESSION_DAYS = 30
MAX_PASSWORD_BYTES = 72
DUMMY_HASH = bcrypt.hashpw(b"no account has this password", bcrypt.gensalt())


def get_db(request: Request):
    """Yield a connection to the app's database, closed after the request."""
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(get_db)]


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds")


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, password_hash):
    """Verify a password against its hash.

    With no hash (unknown email) it still runs one bcrypt check against a dummy,
    so response time does not reveal whether the account exists.
    """
    if password_hash is None:
        bcrypt.checkpw(password.encode(), DUMMY_HASH)
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session(conn, user_id):
    """Store a new random session token for the user and return (token, max_age_seconds).

    Expired sessions are cleared out at the same time.
    """
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    with conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now_iso(),))
        conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    return token, SESSION_DAYS * 24 * 60 * 60


def delete_session(conn, token):
    with conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def current_user(request: Request, db: Db):
    """The signed-in user's row, or 401 when the session cookie is missing, unknown or expired."""
    token = request.cookies.get(COOKIE_NAME)
    row = db.execute(
        "SELECT u.id, u.email, u.name FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token = ? AND s.expires_at > ?",
        (token or "", now_iso()),
    ).fetchone()
    if row is None:
        raise HTTPException(401, "Sign in to continue.")
    return row


CurrentUser = Annotated[sqlite3.Row, Depends(current_user)]
