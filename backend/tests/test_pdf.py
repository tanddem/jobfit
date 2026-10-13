"""Unit tests for PDF text extraction."""

import pytest

from app.pdf import PdfError, extract_text
from conftest import make_pdf


def test_extracts_every_line():
    text = extract_text(make_pdf("Linh Tran", "Senior Backend Engineer"))
    assert "Linh Tran" in text
    assert "Senior Backend Engineer" in text


def test_keeps_parentheses_and_backslashes():
    assert "Ledgerly (2021 - present)" in extract_text(make_pdf("Ledgerly (2021 - present)"))


def test_pdf_without_text_returns_empty_string():
    assert extract_text(make_pdf()) == ""


def test_garbage_raises_pdf_error():
    with pytest.raises(PdfError):
        extract_text(b"%PDF-1.4 this is not really a pdf")
