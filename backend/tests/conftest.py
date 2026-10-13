"""Shared paths, loaders and app fixtures for the test suite."""

import json
from functools import partial
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.scoring import score
from app.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def load_json(path):
    """Read a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def make_pdf(*lines):
    """Build a one-page PDF whose text layer holds the given lines.

    With no lines the page has no text, like a scanned CV.
    """
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    shown = " T* ".join(f"({line}) Tj" for line in escaped)
    stream = f"BT /F1 12 Tf 14 TL 72 720 Td {shown} ET".encode() if lines else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


@pytest.fixture(scope="session")
def rubric():
    """The parsed rubric.json from the project root."""
    return load_json(ROOT / "rubric.json")


@pytest.fixture
def settings(tmp_path):
    """Settings pointing at a throwaway database and a tiny frontend build."""
    static_dir = tmp_path / "out"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>login</h1>")
    return Settings(db_path=tmp_path / "jobfit.sqlite3", static_dir=static_dir)


def model_reply(output):
    """An OpenRouter chat completion body whose message content is output as JSON."""
    return {"choices": [{"message": {"content": json.dumps(output)}}]}


class StubModel:
    """Stands in for OpenRouter: records each payload and replies with canned bodies in turn."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.payloads = []

    def __call__(self, payload, api_key):
        self.payloads.append(payload)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def stub_model():
    """A stub that always returns case-01's hand-made model output."""
    return StubModel(model_reply(load_json(FIXTURES / "case-01-backend-strong" / "scored.json")))


@pytest.fixture
def app(settings, stub_model):
    """A freshly created app scoring through stub_model."""
    return create_app(settings, score_fn=partial(score, api_key="test-key", model="test-model", call=stub_model))


@pytest.fixture
def client(app):
    """A signed-out browser."""
    with TestClient(app) as test_client:
        yield test_client


def register(client, email="linh@example.com", name="Linh Tran", password="correct horse"):
    """Create an account through the API; the client keeps the session cookie."""
    return client.post("/api/auth/register", json={"email": email, "name": name, "password": password})


@pytest.fixture
def signed_in(client):
    """A browser signed in as linh@example.com."""
    assert register(client).status_code == 201
    return client


@pytest.fixture
def other_user(app):
    """A second browser, signed in as a different account."""
    with TestClient(app) as test_client:
        assert register(test_client, email="minh@example.com", name="Minh").status_code == 201
        yield test_client
