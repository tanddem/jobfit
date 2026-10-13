"""HTTP API: health check, fake login and CV/JD upload."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints

from app.db import connect
from app.pdf import PdfError, extract_text

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_BODY_BYTES = MAX_PDF_BYTES + 1024 * 1024
MAX_JD_CHARS = 50_000
TOO_LARGE = "The CV must be 5 MB or smaller."

router = APIRouter(prefix="/api")


def get_db(request: Request):
    """Yield a connection to the app's database, closed after the request."""
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(get_db)]


async def limit_upload_size(request: Request, call_next):
    """Reject oversized uploads from Content-Length, before the body is received."""
    declared = int(request.headers.get("content-length") or 0)
    if request.url.path == "/api/uploads" and declared > MAX_UPLOAD_BODY_BYTES:
        return JSONResponse({"detail": TOO_LARGE}, status_code=413)
    return await call_next(request)


class SessionRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class SessionResponse(BaseModel):
    user_id: int
    name: str


class UploadResponse(BaseModel):
    upload_id: int
    filename: str
    cv_text: str
    jd_text: str


@router.get("/health")
def health():
    """Liveness probe."""
    return {"status": "ok"}


@router.post("/session", response_model=SessionResponse)
def create_session(body: SessionRequest, db: Db):
    """Fake login: create a user from a name and return its id."""
    with db:
        user_id = db.execute("INSERT INTO users (name) VALUES (?)", (body.name,)).lastrowid
    return SessionResponse(user_id=user_id, name=body.name)


@router.post("/uploads", response_model=UploadResponse)
def create_upload(
    db: Db,
    user_id: Annotated[int, Form()],
    jd_text: Annotated[str, Form(max_length=MAX_JD_CHARS)],
    cv: Annotated[UploadFile, File()],
):
    """Store a CV PDF's extracted text alongside a pasted job description."""
    if db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
        raise HTTPException(422, "Unknown user.")
    jd_text = jd_text.strip()
    if not jd_text:
        raise HTTPException(422, "Paste a job description.")

    data = cv.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, TOO_LARGE)
    if not data.startswith(b"%PDF-"):
        raise HTTPException(400, "The CV must be a PDF file.")
    try:
        cv_text = extract_text(data)
    except PdfError:
        raise HTTPException(400, "The PDF could not be read.")
    if not cv_text:
        raise HTTPException(422, "No text found in the PDF. Scanned CVs are not supported yet.")

    filename = cv.filename or "cv.pdf"
    with db:
        upload_id = db.execute(
            "INSERT INTO uploads (user_id, filename, cv_text, jd_text) VALUES (?, ?, ?, ?)",
            (user_id, filename, cv_text, jd_text),
        ).lastrowid
    return UploadResponse(upload_id=upload_id, filename=filename, cv_text=cv_text, jd_text=jd_text)
