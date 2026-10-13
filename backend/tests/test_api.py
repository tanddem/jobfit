"""Integration tests for the HTTP API and frontend serving."""

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO

import httpx2
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from app.api import MAX_JD_CHARS, MAX_PDF_BYTES, MAX_UPLOAD_BODY_BYTES
from app.db import connect
from app.main import create_app
from app.scoring import score
from app.settings import Settings
from conftest import StubModel, make_pdf

JD = "Senior Backend Engineer. 5+ years of Python."


@pytest.fixture
def user_id(client):
    return client.post("/api/session", json={"name": "Linh"}).json()["user_id"]


def upload(client, user_id, pdf, jd=JD, filename="cv.pdf"):
    return client.post(
        "/api/uploads",
        data={"user_id": str(user_id), "jd_text": jd},
        files={"cv": (filename, pdf, "application/pdf")},
    )


def encrypt(pdf, password):
    """Return pdf encrypted with AES-256 under the given user password."""
    writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf)))
    writer.encrypt(password, owner_password="owner", algorithm="AES-256")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_session_creates_user(client, settings):
    response = client.post("/api/session", json={"name": "  Linh Tran  "})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Linh Tran"
    conn = connect(settings.db_path)
    assert conn.execute("SELECT name FROM users WHERE id = ?", (body["user_id"],)).fetchone()["name"] == "Linh Tran"
    conn.close()


@pytest.mark.parametrize("name", ["", "   "])
def test_session_rejects_blank_name(client, name):
    assert client.post("/api/session", json={"name": name}).status_code == 422


def test_upload_extracts_and_stores_cv_text(client, settings, user_id):
    response = upload(client, user_id, make_pdf("Linh Tran", "Python, FastAPI"))
    assert response.status_code == 200
    body = response.json()
    assert "Python, FastAPI" in body["cv_text"]
    assert body["jd_text"] == JD
    assert body["filename"] == "cv.pdf"

    conn = connect(settings.db_path)
    row = conn.execute("SELECT * FROM uploads WHERE id = ?", (body["upload_id"],)).fetchone()
    conn.close()
    assert row["user_id"] == user_id
    assert row["cv_text"] == body["cv_text"]


def test_upload_rejects_unknown_user(client):
    response = upload(client, 999, make_pdf("Linh"))
    assert response.status_code == 422
    assert response.json()["detail"] == "Unknown user."


def test_upload_rejects_blank_jd(client, user_id):
    assert upload(client, user_id, make_pdf("Linh"), jd="   ").status_code == 422


def test_upload_rejects_non_pdf(client, user_id):
    response = upload(client, user_id, b"just some text", filename="cv.txt")
    assert response.status_code == 400


def test_upload_rejects_unreadable_pdf(client, user_id):
    assert upload(client, user_id, b"%PDF-1.4 broken").status_code == 400


def test_upload_rejects_oversized_file(client, user_id):
    response = upload(client, user_id, b"%PDF-" + b"0" * MAX_PDF_BYTES)
    assert response.status_code == 413


def test_upload_rejects_pdf_without_text(client, user_id):
    response = upload(client, user_id, make_pdf())
    assert response.status_code == 422
    assert "No text" in response.json()["detail"]


def test_failed_upload_stores_nothing(client, settings, user_id):
    upload(client, user_id, make_pdf())
    conn = connect(settings.db_path)
    assert conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] == 0
    conn.close()


def test_serves_frontend_at_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "login" in response.text


def test_app_boots_without_frontend_build(settings, tmp_path):
    bare = Settings(db_path=settings.db_path, static_dir=tmp_path / "missing")
    with TestClient(create_app(bare)) as bare_client:
        assert bare_client.get("/api/health").status_code == 200
        assert bare_client.get("/").status_code == 404


def test_concurrent_requests_share_the_threadpool(client):
    """Each request's connection may be opened and closed on different worker threads."""
    with ThreadPoolExecutor(16) as pool:
        codes = list(pool.map(lambda i: client.post("/api/session", json={"name": f"u{i}"}).status_code, range(200)))
    assert set(codes) == {200}


def test_upload_reads_pdf_encrypted_with_empty_password(client, user_id):
    response = upload(client, user_id, encrypt(make_pdf("Linh Tran"), ""))
    assert response.status_code == 200
    assert "Linh Tran" in response.json()["cv_text"]


def test_upload_rejects_password_protected_pdf(client, user_id):
    assert upload(client, user_id, encrypt(make_pdf("Linh Tran"), "secret")).status_code == 400


def test_upload_rejects_declared_oversized_body_before_reading(client):
    response = client.post(
        "/api/uploads",
        content=b"x",
        headers={"content-type": "multipart/form-data; boundary=b", "content-length": str(MAX_UPLOAD_BODY_BYTES + 1)},
    )
    assert response.status_code == 413


def test_upload_rejects_overlong_jd(client, user_id):
    assert upload(client, user_id, make_pdf("Linh"), jd="x" * (MAX_JD_CHARS + 1)).status_code == 422


def test_upload_returns_and_stores_the_score(client, user_id):
    body = upload(client, user_id, make_pdf("Linh Tran", "Python, FastAPI, Kafka")).json()
    score = body["score"]
    # Case-01 facts on a two-line CV: skills 28, experience 100, achievements 89,
    # education 100, structure 20 (no headings, no year) -> 64.6 -> 65.
    assert score["overall"] == 65
    assert score["band"] == "partial"
    assert "Python" in score["matched_keywords"]
    assert client.get(f"/api/uploads/{body['upload_id']}/score").json() == score


def test_scoring_failure_returns_502_and_stores_nothing(settings):
    failing = partial(score, api_key="k", model="m", call=StubModel(httpx2.ConnectError("down")))
    with TestClient(create_app(settings, score_fn=failing)) as failing_client:
        uid = failing_client.post("/api/session", json={"name": "Linh"}).json()["user_id"]
        response = upload(failing_client, uid, make_pdf("Linh Tran"))
    assert response.status_code == 502
    conn = connect(settings.db_path)
    assert conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] == 0
    conn.close()


def test_score_for_unknown_upload_is_404(client):
    assert client.get("/api/uploads/999/score").status_code == 404
