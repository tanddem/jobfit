"""Scored CV/JD uploads, grouped by company and role, owned by the signed-in user."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import CurrentUser, Db
from app.pdf import PdfError, extract_text
from app.scoring import ScoreResult, ScoringError

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_BODY_BYTES = MAX_PDF_BYTES + 1024 * 1024
MAX_JD_CHARS = 50_000
MAX_LABEL_CHARS = 200
TOO_LARGE = "The CV must be 5 MB or smaller."

router = APIRouter(prefix="/api/uploads")


async def limit_upload_size(request: Request, call_next):
    """Reject oversized uploads from Content-Length, before the body is received."""
    declared = int(request.headers.get("content-length") or 0)
    if request.url.path == "/api/uploads" and request.method == "POST" and declared > MAX_UPLOAD_BODY_BYTES:
        return JSONResponse({"detail": TOO_LARGE}, status_code=413)
    return await call_next(request)


class UploadSummary(BaseModel):
    upload_id: int
    company: str
    role_title: str
    filename: str
    created_at: str
    overall: int
    band: str


class UploadDetail(UploadSummary):
    cv_text: str
    jd_text: str
    score: ScoreResult


UPLOAD_COLUMNS = "u.id, u.company, u.role_title, u.filename, u.created_at, u.cv_text, u.jd_text, s.result_json"


def to_detail(row):
    """An uploads row joined with its score, as an UploadDetail."""
    score = ScoreResult.model_validate_json(row["result_json"])
    return UploadDetail(
        upload_id=row["id"],
        company=row["company"],
        role_title=row["role_title"],
        filename=row["filename"],
        created_at=row["created_at"],
        overall=score.overall,
        band=score.band,
        cv_text=row["cv_text"],
        jd_text=row["jd_text"],
        score=score,
    )


def owned_upload(db, user, upload_id):
    """The user's upload joined with its score, or 404 for anyone else's or a missing one."""
    row = db.execute(
        f"SELECT {UPLOAD_COLUMNS} FROM uploads u JOIN scores s ON s.key = u.score_key WHERE u.id = ? AND u.user_id = ?",
        (upload_id, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Upload not found.")
    return row


def required_text(value, message):
    value = value.strip()
    if not value:
        raise HTTPException(422, message)
    return value


@router.post("", response_model=UploadDetail)
def create_upload(
    request: Request,
    db: Db,
    user: CurrentUser,
    company: Annotated[str, Form(max_length=MAX_LABEL_CHARS)],
    role_title: Annotated[str, Form(max_length=MAX_LABEL_CHARS)],
    jd_text: Annotated[str, Form(max_length=MAX_JD_CHARS)],
    cv: Annotated[UploadFile, File()],
):
    """Extract a CV PDF's text, score it against the pasted JD, and store it under company and role.

    Scoring runs before anything is saved, so a scoring failure leaves no upload.
    """
    company = required_text(company, "Enter the company name.")
    role_title = required_text(role_title, "Enter the role title.")
    jd_text = required_text(jd_text, "Paste a job description.")

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

    try:
        score_key, _ = request.app.state.score_fn(cv_text, jd_text, conn=db)
    except ScoringError:
        raise HTTPException(502, "Scoring is unavailable right now. Please try again.")

    with db:
        upload_id = db.execute(
            "INSERT INTO uploads (user_id, company, role_title, filename, cv_text, jd_text, score_key) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"], company, role_title, cv.filename or "cv.pdf", cv_text, jd_text, score_key),
        ).lastrowid
    return to_detail(owned_upload(db, user, upload_id))


@router.get("", response_model=list[UploadSummary])
def list_uploads(db: Db, user: CurrentUser, company: str | None = None, role: str | None = None):
    """The user's uploads, newest first, optionally for one company and role."""
    query = f"SELECT {UPLOAD_COLUMNS} FROM uploads u JOIN scores s ON s.key = u.score_key WHERE u.user_id = ?"
    params = [user["id"]]
    if company is not None:
        query += " AND u.company = ?"
        params.append(company)
    if role is not None:
        query += " AND u.role_title = ?"
        params.append(role)
    rows = db.execute(query + " ORDER BY u.created_at DESC, u.id DESC", params).fetchall()
    return [UploadSummary.model_validate(to_detail(row), from_attributes=True) for row in rows]


@router.get("/{upload_id}", response_model=UploadDetail)
def read_upload(upload_id: int, db: Db, user: CurrentUser):
    """One of the user's uploads with its CV text, JD and score."""
    return to_detail(owned_upload(db, user, upload_id))


@router.get("/{upload_id}/score", response_model=ScoreResult)
def read_score(upload_id: int, db: Db, user: CurrentUser):
    """The stored score for one of the user's uploads."""
    return ScoreResult.model_validate_json(owned_upload(db, user, upload_id)["result_json"])


@router.delete("/{upload_id}", status_code=204)
def delete_upload(upload_id: int, db: Db, user: CurrentUser):
    """Delete one of the user's uploads. The cached score stays for reuse."""
    owned_upload(db, user, upload_id)
    with db:
        db.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
