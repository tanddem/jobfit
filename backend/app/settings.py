"""Runtime settings read from the environment."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Where the database lives and where the built frontend is served from."""

    db_path: Path
    static_dir: Path

    @classmethod
    def from_env(cls):
        """Build settings from JOBFIT_DB_PATH and JOBFIT_STATIC_DIR, with local defaults."""
        return cls(
            db_path=Path(os.environ.get("JOBFIT_DB_PATH", ROOT / "data" / "jobfit.sqlite3")),
            static_dir=Path(os.environ.get("JOBFIT_STATIC_DIR", ROOT / "frontend" / "out")),
        )
