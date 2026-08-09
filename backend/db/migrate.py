"""
backend/db/migrate.py

Programmatic Alembic entrypoint. Runs `alembic upgrade head` against the
app's resolved DATABASE_URL (same source of truth as the runtime engine in
backend/db/database.py). Used at app startup and can be invoked standalone:

    venv/bin/python -m backend.db.migrate
"""

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
SCRIPT_LOCATION = REPO_ROOT / "migrations"


def _alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(SCRIPT_LOCATION))
    return cfg


def run_migrations() -> None:
    """Upgrade the database to head. Safe to call on every startup."""
    # In-app migration runs must not let alembic.ini's logging config replace
    # the app's root handlers (backend.log); keep alembic itself quiet too.
    os.environ["NORAI_MIGRATE_NO_LOGGING"] = "1"
    logging.getLogger("alembic").setLevel(logging.WARNING)
    command.upgrade(_alembic_config(), "head")


if __name__ == "__main__":
    run_migrations()
