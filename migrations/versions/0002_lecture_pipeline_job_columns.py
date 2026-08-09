"""P4.1 — add DB-backed job queue columns to lectures

Revision ID: 0002_job_queue_columns
Revises: 0001_initial_schema
Create Date: 2026-08-09

Each ADD COLUMN is guarded by an inspector check so this migration is safe on
fresh DBs (rev 0001 just created `lectures`), on pre-Alembic DBs (tables made
by create_all), and when re-run.

NOTE: the revision id must stay <= 32 chars — Postgres's alembic_version
column is VARCHAR(32) and a longer id truncates at runtime.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_job_queue_columns"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

# name -> (column type, server_default or None). Non-null columns carry a
# server_default so existing rows are backfilled. sa.false()/sa.text("0")
# render dialect-safe literals for both PostgreSQL and SQLite.
_PIPELINE_COLUMNS = [
    ("stage", sa.String(length=64), None),
    ("stage_message", sa.Text(), None),
    ("progress", sa.Float(), None),
    ("attempts", sa.Integer(), sa.text("0")),
    ("heartbeat_at", sa.DateTime(timezone=True), None),
    ("queued_at", sa.DateTime(timezone=True), None),
    ("started_at", sa.DateTime(timezone=True), None),
    ("cancel_requested", sa.Boolean(), sa.false()),
]


def _has_column(table: str, column: str) -> bool:
    try:
        insp = sa.inspect(op.get_bind())
    except Exception:
        # Offline mode (`alembic upgrade --sql`) has no real bind — assume the
        # column is absent so the DDL is emitted for review.
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    for name, col_type, default in _PIPELINE_COLUMNS:
        if _has_column("lectures", name):
            continue
        kwargs = {"nullable": True}
        if default is not None:
            kwargs["nullable"] = False
            kwargs["server_default"] = default
        op.add_column("lectures", sa.Column(name, col_type, **kwargs))


def downgrade() -> None:
    for name, _col_type, _default in reversed(_PIPELINE_COLUMNS):
        if _has_column("lectures", name):
            op.drop_column("lectures", name)
