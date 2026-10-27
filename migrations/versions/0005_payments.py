"""Razorpay payments

Revision ID: 0005_payments
Revises: 0004_courses_and_shares
Create Date: 2026-10-27

Adds `payments` (one row per Razorpay order for a plan pass). Guarded by an
inspector check like 0003/0004 so it is safe on fresh DBs, legacy
create_all DBs, and when re-run.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_payments"
down_revision = "0004_courses_and_shares"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    try:
        insp = sa.inspect(op.get_bind())
    except Exception:
        return False
    return table in insp.get_table_names()


def upgrade() -> None:
    if _has_table("payments"):
        return
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.String(length=32), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("razorpay_payment_id", sa.String(length=64), nullable=True),
        sa.Column("method", sa.String(length=32), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("refunded_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_razorpay_payment_id", "payments", ["razorpay_payment_id"])


def downgrade() -> None:
    if _has_table("payments"):
        op.drop_table("payments")
