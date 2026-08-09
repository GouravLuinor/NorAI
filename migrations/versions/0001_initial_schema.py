"""initial schema — users, subscriptions, lectures, usage_logs, webhook_events

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-09

Mirrors what `Base.metadata.create_all` previously produced so DBs created
before Alembic existed are absorbed as a no-op (all tables use
`if_not_exists=True`).
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("plan_tier", sa.String(length=32), nullable=False),
        sa.Column("lemon_squeezy_customer_id", sa.String(length=128), nullable=True),
        sa.Column("lemon_squeezy_subscription_id", sa.String(length=128), nullable=True),
        sa.Column("monthly_minutes_quota", sa.Integer(), nullable=False),
        sa.Column("used_minutes_this_month", sa.Integer(), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "lectures",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("output_dir", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "usage_logs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lecture_id",
            sa.String(length=128),
            sa.ForeignKey("lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )

    # Indexes are created separately with if_not_exists so re-absorbing a
    # pre-Alembic DB (where CREATE TABLE IF NOT EXISTS is a no-op but its
    # inline index would still be attempted) never trips on existing indexes.
    op.create_index("ix_users_email", "users", ["email"], unique=True, if_not_exists=True)
    op.create_index("ix_lectures_user_id", "lectures", ["user_id"], if_not_exists=True)
    op.create_index("ix_usage_logs_user_id", "usage_logs", ["user_id"], if_not_exists=True)
    op.create_index("ix_usage_logs_lecture_id", "usage_logs", ["lecture_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_table("webhook_events", if_exists=True)
    op.drop_table("usage_logs", if_exists=True)
    op.drop_table("lectures", if_exists=True)
    op.drop_table("subscriptions", if_exists=True)
    op.drop_table("users", if_exists=True)
