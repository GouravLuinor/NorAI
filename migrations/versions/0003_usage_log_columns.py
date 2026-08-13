"""P6.5 — add cost-dashboard columns to usage_logs

Revision ID: 0003_usage_log_columns
Revises: 0002_job_queue_columns
Create Date: 2026-08-13

Adds `model` (the Gemini model the call used) and `calls` (number of API calls
rolled into the row) to `usage_logs`. Both are additive; guarded by inspector
checks like 0002 so they are safe on fresh DBs, legacy create_all DBs, and when
re-run.

NOTE: the revision id must stay <= 32 chars — Postgres's alembic_version
column is VARCHAR(32).
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_usage_log_columns"
down_revision = "0002_job_queue_columns"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    try:
        insp = sa.inspect(op.get_bind())
    except Exception:
        # Offline mode (`alembic upgrade --sql`) has no real bind — assume the
        # column is absent so the DDL is emitted for review.
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("usage_logs", "model"):
        op.add_column("usage_logs", sa.Column("model", sa.String(length=64), nullable=True))
    if not _has_column("usage_logs", "calls"):
        op.add_column("usage_logs", sa.Column("calls", sa.Integer(), server_default=sa.text("0"), nullable=False))


def downgrade() -> None:
    for column in ("calls", "model"):
        if _has_column("usage_logs", column):
            op.drop_column("usage_logs", column)
