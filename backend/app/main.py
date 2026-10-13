"""Application factory: the API plus the statically exported frontend on one port."""

from functools import partial

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import auth, uploads
from app.scoring import score
from app.settings import Settings


def create_app(settings=None, score_fn=None):
    """Bring the database schema up to date, mount the API, and serve the frontend build if present.

    score_fn(cv_text, jd_text, conn=...) -> (cache key, ScoreResult) defaults to
    the OpenRouter scorer; tests inject their own.
    """
    settings = settings or Settings.from_env()
    init_db(settings.db_path)

    app = FastAPI(title="JobFit")
    app.state.settings = settings
    app.state.score_fn = score_fn or partial(
        score, api_key=settings.openrouter_api_key, model=settings.openrouter_model
    )
    app.middleware("http")(uploads.limit_upload_size)

    @app.get("/api/health")
    def health():
        """Liveness probe."""
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(uploads.router)
    if settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")
    return app
