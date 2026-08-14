"""P6.4 — courses + share links

Revision ID: 0004_courses_and_shares
Revises: 0003_usage_log_columns
Create Date: 2026-08-13

Adds:
- courses             (id, user_id, name, description, timestamps)
- course_lectures     join (course_id, lecture_id, position) — ordered membership
- share_links         (id = unguessable slug, lecture_id, created_by,
                       allow_tutor_chat, expires_at, created_at)

All guarded by inspector checks like 0003 so they are safe on fresh DBs,
legacy create_all DBs, and when re-run. Course membership delete-orphans with
the course; share links cascade with the lecture/user.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_courses_and_shares"
down_revision = "0003_usage_log_columns"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    try:
        insp = sa.inspect(op.get_bind())
    except Exception:
        # Offline mode (`alembic upgrade --sql`) has no real bind — assume the
        # table is absent so the DDL is emitted for review.
        return False
    return table in insp.get_table_names()


def upgrade() -> None:
    if not _has_table("courses"):
        op.create_table(
            "courses",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(length=64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=256), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_courses_user_id", "courses", ["user_id"])

    if not _has_table("course_lectures"):
        op.create_table(
            "course_lectures",
            sa.Column(
                "course_id",
                sa.String(length=64),
                sa.ForeignKey("courses.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "lecture_id",
                sa.String(length=128),
                sa.ForeignKey("lectures.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has_table("share_links"):
        op.create_table(
            "share_links",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column(
                "lecture_id",
                sa.String(length=128),
                sa.ForeignKey("lectures.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_by",
                sa.String(length=64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("allow_tutor_chat", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_share_links_lecture_id", "share_links", ["lecture_id"])
        op.create_index("ix_share_links_created_by", "share_links", ["created_by"])


def downgrade() -> None:
    for table in ("share_links", "course_lectures", "courses"):
        if _has_table(table):
            op.drop_table(table)