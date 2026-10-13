"""Shared paths, loaders and app fixtures for the test suite."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
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


@pytest.fixture
def client(settings):
    """A test client for a freshly created app."""
    with TestClient(create_app(settings)) as test_client:
        yield test_client
