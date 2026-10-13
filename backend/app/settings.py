"""Runtime settings read from the environment and the project's .env file."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Where data lives, where the frontend is served from, and how to reach OpenRouter."""

    db_path: Path
    static_dir: Path
    openrouter_api_key: str = ""
    openrouter_model: str = ""

    @classmethod
    def from_env(cls):
        """Build settings from the environment, after loading ROOT/.env if present.

        Variables already set in the environment win over .env.
        """
        load_dotenv(ROOT / ".env")
        return cls(
            db_path=Path(os.environ.get("JOBFIT_DB_PATH", ROOT / "data" / "jobfit.sqlite3")),
            static_dir=Path(os.environ.get("JOBFIT_STATIC_DIR", ROOT / "frontend" / "out")),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            openrouter_model=os.environ.get("OPENROUTER_MODEL", ""),
        )
