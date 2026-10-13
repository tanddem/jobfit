"""Text extraction from uploaded CV PDFs."""

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError


class PdfError(Exception):
    """The upload could not be read as a PDF."""


def extract_text(data):
    """Return the text of every page, joined by newlines and stripped.

    An empty string means the PDF has no text layer, such as a scanned image.
    Raises PdfError for unreadable or password-protected files.
    """
    try:
        reader = PdfReader(BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except PyPdfError as exc:
        raise PdfError(str(exc)) from exc
    return "\n".join(pages).strip()
