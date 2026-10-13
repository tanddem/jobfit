"""Integration and unit tests for accounts and sessions."""

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, check_password, hash_password
from app.db import connect
from app.main import create_app
from conftest import register


def test_register_signs_in_with_http_only_cookie(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json()["email"] == "linh@example.com"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=2592000" in cookie
    assert client.get("/api/auth/me").json()["name"] == "Linh Tran"


def test_password_is_stored_hashed(signed_in, settings):
    conn = connect(settings.db_path)
    stored = conn.execute("SELECT password_hash FROM users").fetchone()["password_hash"]
    conn.close()
    assert stored != "correct horse"
    assert check_password("correct horse", stored)


def test_duplicate_email_is_rejected_ignoring_case(signed_in):
    response = register(signed_in, email="LINH@example.com")
    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "name": "Linh", "password": "correct horse"},
        {"email": "a@example.com", "name": "  ", "password": "correct horse"},
        {"email": "a@example.com", "name": "Linh", "password": "short"},
        {"email": "a@example.com", "name": "Linh", "password": "x" * 73},
    ],
)
def test_register_validates_input(client, body):
    assert client.post("/api/auth/register", json=body).status_code == 422


def test_logout_then_login_again(signed_in):
    assert signed_in.post("/api/auth/logout").status_code == 204
    assert signed_in.get("/api/auth/me").status_code == 401

    response = signed_in.post("/api/auth/login", json={"email": "Linh@Example.com", "password": "correct horse"})
    assert response.status_code == 200
    assert signed_in.get("/api/auth/me").json()["email"] == "linh@example.com"


def test_logout_invalidates_the_token_server_side(signed_in):
    token = signed_in.cookies[COOKIE_NAME]
    signed_in.post("/api/auth/logout")
    signed_in.cookies.set(COOKIE_NAME, token)
    assert signed_in.get("/api/auth/me").status_code == 401


def test_wrong_password_and_unknown_email_get_the_same_answer(signed_in):
    signed_in.post("/api/auth/logout")
    wrong = signed_in.post("/api/auth/login", json={"email": "linh@example.com", "password": "wrong password"})
    unknown = signed_in.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_unknown_email_still_runs_bcrypt(signed_in):
    """Login time must not reveal whether an account exists."""
    signed_in.post("/api/auth/logout")

    def timed(email):
        start = time.perf_counter()
        signed_in.post("/api/auth/login", json={"email": email, "password": "wrong password"})
        return time.perf_counter() - start

    known = min(timed("linh@example.com") for _ in range(3))
    unknown = min(timed("nobody@example.com") for _ in range(3))
    assert unknown > known / 3


def test_overlong_login_password_is_rejected_not_crashed(signed_in):
    response = signed_in.post("/api/auth/login", json={"email": "linh@example.com", "password": "x" * 100})
    assert response.status_code == 422


def test_expired_session_is_rejected(signed_in, settings):
    conn = connect(settings.db_path)
    with conn:
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    conn.close()
    assert signed_in.get("/api/auth/me").status_code == 401


def test_me_without_cookie_is_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_check_password_rejects_missing_hash_even_for_dummy_password():
    assert not check_password("no account has this password", None)
    assert check_password("pw", hash_password("pw"))


def test_concurrent_duplicate_registration_is_409_not_500(app):
    body = {"email": "race@example.com", "name": "R", "password": "correct horse"}
    with TestClient(app, raise_server_exceptions=False) as browser:
        with ThreadPoolExecutor(8) as pool:
            codes = sorted(pool.map(lambda _: browser.post("/api/auth/register", json=body).status_code, range(8)))
    assert codes == [201] + [409] * 7


def test_cookie_is_secure_when_configured(settings, stub_model):
    secure = create_app(replace(settings, cookie_secure=True))
    with TestClient(secure) as browser:
        assert "Secure" in register(browser).headers["set-cookie"]


def test_signing_in_clears_expired_sessions(signed_in, settings):
    conn = connect(settings.db_path)
    with conn:
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    conn.close()
    signed_in.post("/api/auth/login", json={"email": "linh@example.com", "password": "correct horse"})
    conn = connect(settings.db_path)
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    conn.close()
