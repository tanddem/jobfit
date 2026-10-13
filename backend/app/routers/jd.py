"""Fetch a job description from a link, for a signed-in user."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import CurrentUser
from app.jd_fetch import FetchedJd, JdFetchError

router = APIRouter(prefix="/api/jd")


class FetchRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


@router.post("/fetch", response_model=FetchedJd)
def fetch(body: FetchRequest, request: Request, user: CurrentUser):
    """Return the job description text found at the link, for the user to check before scoring."""
    try:
        return request.app.state.jd_fetch_fn(body.url)
    except JdFetchError as exc:
        raise HTTPException(exc.status_code, str(exc))
