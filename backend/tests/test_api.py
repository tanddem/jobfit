"""Integration tests for uploads, scoring through the API, and frontend serving."""

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO

import httpx2
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from app.db import connect
from app.main import create_app
from app.routers.uploads import MAX_JD_CHARS, MAX_PDF_BYTES, MAX_UPLOAD_BODY_BYTES
from app.scoring import score
from app.settings import Settings
from conftest import StubModel, make_pdf, register

JD = "Senior Backend Engineer. 5+ years of Python."


def upload(client, pdf=None, jd=JD, filename="cv.pdf", company="Northwind", role="Backend Engineer"):
    return client.post(
        "/api/uploads",
        data={"company": company, "role_title": role, "jd_text": jd},
        files={"cv": (filename, pdf if pdf is not None else make_pdf("Linh Tran", "Python"), "application/pdf")},
    )


def encrypt(pdf, password):
    """Return pdf encrypted with AES-256 under the given user password."""
    writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf)))
    writer.encrypt(password, owner_password="owner", algorithm="AES-256")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def count_uploads(settings):
    conn = connect(settings.db_path)
    count = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
    conn.close()
    return count


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "method, path",
    [("post", "/api/uploads"), ("get", "/api/uploads"), ("get", "/api/uploads/1"), ("get", "/api/uploads/1/score"), ("delete", "/api/uploads/1")],
)
def test_uploads_require_sign_in(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_upload_extracts_scores_and_stores_under_company_and_role(signed_in, settings):
    response = upload(signed_in, make_pdf("Linh Tran", "Python, FastAPI"))
    assert response.status_code == 200
    body = response.json()
    assert "Python, FastAPI" in body["cv_text"]
    assert (body["company"], body["role_title"], body["jd_text"], body["filename"]) == ("Northwind", "Backend Engineer", JD, "cv.pdf")

    conn = connect(settings.db_path)
    row = conn.execute("SELECT u.*, users.email FROM uploads u JOIN users ON users.id = u.user_id WHERE u.id = ?", (body["upload_id"],)).fetchone()
    conn.close()
    assert row["email"] == "linh@example.com"
    assert row["cv_text"] == body["cv_text"]


def test_upload_returns_and_stores_the_score(signed_in):
    body = upload(signed_in, make_pdf("Linh Tran", "Python, FastAPI, Kafka")).json()
    score = body["score"]
    # Case-01 facts on a two-line CV: skills 28, experience 100, achievements 89,
    # education 100, structure 20 (no headings, no year) -> 64.6 -> 65.
    assert score["overall"] == 65
    assert score["band"] == "partial"
    assert "Python" in score["matched_keywords"]
    assert signed_in.get(f"/api/uploads/{body['upload_id']}/score").json() == score


@pytest.mark.parametrize("field", ["company", "role", "jd"])
def test_upload_rejects_blank_labels_and_jd(signed_in, field):
    assert upload(signed_in, **{field: "   "}).status_code == 422


def test_upload_rejects_non_pdf(signed_in):
    assert upload(signed_in, b"just some text", filename="cv.txt").status_code == 400


def test_upload_rejects_unreadable_pdf(signed_in):
    assert upload(signed_in, b"%PDF-1.4 broken").status_code == 400


def test_upload_rejects_oversized_file(signed_in):
    assert upload(signed_in, b"%PDF-" + b"0" * MAX_PDF_BYTES).status_code == 413


def test_upload_rejects_declared_oversized_body_before_reading(signed_in):
    response = signed_in.post(
        "/api/uploads",
        content=b"x",
        headers={"content-type": "multipart/form-data; boundary=b", "content-length": str(MAX_UPLOAD_BODY_BYTES + 1)},
    )
    assert response.status_code == 413


def test_upload_rejects_overlong_jd(signed_in):
    assert upload(signed_in, jd="x" * (MAX_JD_CHARS + 1)).status_code == 422


def test_upload_rejects_pdf_without_text_and_stores_nothing(signed_in, settings):
    response = upload(signed_in, make_pdf())
    assert response.status_code == 422
    assert "No text" in response.json()["detail"]
    assert count_uploads(settings) == 0


def test_upload_reads_pdf_encrypted_with_empty_password(signed_in):
    response = upload(signed_in, encrypt(make_pdf("Linh Tran"), ""))
    assert response.status_code == 200
    assert "Linh Tran" in response.json()["cv_text"]


def test_upload_rejects_password_protected_pdf(signed_in):
    assert upload(signed_in, encrypt(make_pdf("Linh Tran"), "secret")).status_code == 400


def test_scoring_failure_returns_502_and_stores_nothing(settings):
    failing = partial(score, api_key="k", model="m", call=StubModel(httpx2.ConnectError("down")))
    with TestClient(create_app(settings, score_fn=failing)) as failing_client:
        register(failing_client)
        response = upload(failing_client)
    assert response.status_code == 502
    assert count_uploads(settings) == 0


def test_list_is_newest_first_and_filters_by_company_and_role(signed_in):
    first = upload(signed_in, company="Northwind", role="Backend Engineer").json()["upload_id"]
    second = upload(signed_in, company="Northwind", role="Backend Engineer").json()["upload_id"]
    other = upload(signed_in, company="Brightleaf", role="Marketing Manager").json()["upload_id"]

    listed = signed_in.get("/api/uploads").json()
    assert [u["upload_id"] for u in listed] == [other, second, first]
    assert set(listed[0]) == {"upload_id", "company", "role_title", "filename", "created_at", "overall", "band"}

    filtered = signed_in.get("/api/uploads", params={"company": "Northwind", "role": "Backend Engineer"}).json()
    assert [u["upload_id"] for u in filtered] == [second, first]


def test_read_upload_detail(signed_in):
    upload_id = upload(signed_in).json()["upload_id"]
    detail = signed_in.get(f"/api/uploads/{upload_id}").json()
    assert detail["upload_id"] == upload_id
    assert detail["score"]["band"] in {"strong", "partial", "weak"}


def test_delete_removes_only_that_upload(signed_in):
    keep = upload(signed_in).json()["upload_id"]
    drop = upload(signed_in).json()["upload_id"]
    assert signed_in.delete(f"/api/uploads/{drop}").status_code == 204
    assert [u["upload_id"] for u in signed_in.get("/api/uploads").json()] == [keep]
    assert signed_in.get(f"/api/uploads/{drop}").status_code == 404


def test_other_users_cannot_see_or_delete_my_uploads(signed_in, other_user):
    upload_id = upload(signed_in).json()["upload_id"]
    assert other_user.get("/api/uploads").json() == []
    for method, path in [("get", f"/api/uploads/{upload_id}"), ("get", f"/api/uploads/{upload_id}/score"), ("delete", f"/api/uploads/{upload_id}")]:
        assert getattr(other_user, method)(path).status_code == 404
    assert signed_in.get(f"/api/uploads/{upload_id}").status_code == 200


def test_serves_frontend_at_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "login" in response.text


def test_app_boots_without_frontend_build(settings, tmp_path):
    bare = Settings(db_path=settings.db_path, static_dir=tmp_path / "missing")
    with TestClient(create_app(bare)) as bare_client:
        assert bare_client.get("/api/health").status_code == 200
        assert bare_client.get("/").status_code == 404


def test_concurrent_requests_share_the_threadpool(signed_in):
    """Each request's connection may be opened and closed on different worker threads."""
    with ThreadPoolExecutor(16) as pool:
        codes = list(pool.map(lambda _: signed_in.get("/api/auth/me").status_code, range(200)))
    assert set(codes) == {200}
