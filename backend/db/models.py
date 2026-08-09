"""
backend/db/models.py

SQLAlchemy 2.0 ORM models for NorAI SaaS foundation:
- User
- Subscription
- Lecture
- UsageLog
- WebhookEvent
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    lectures: Mapped[List["Lecture"]] = relationship("Lecture", back_populates="user", cascade="all, delete-orphan")
    usage_logs: Mapped[List["UsageLog"]] = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    status: Mapped[str] = mapped_column(String(32), default="trial")  # 'trial', 'active', 'cancelled', 'past_due'
    plan_tier: Mapped[str] = mapped_column(String(32), default="free")  # 'free', 'starter', 'pro'
    
    lemon_squeezy_customer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lemon_squeezy_subscription_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    
    monthly_minutes_quota: Mapped[int] = mapped_column(Integer, default=15)  # 15 mins for free trial, 300 for starter, 1500 for pro
    used_minutes_this_month: Mapped[int] = mapped_column(Integer, default=0)
    
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscription")


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # lecture_id slug / UUID
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    
    title: Mapped[str] = mapped_column(String(512), default="Untitled Lecture")
    source_type: Mapped[str] = mapped_column(String(32), default="upload")  # 'youtube', 'gdrive', 'upload'
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="processing")  # 'queued', 'processing', 'completed', 'failed', 'cancelled'
    
    output_dir: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # P4.1 — DB-backed job queue fields (updated by the pipeline worker).
    stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    stage_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="lectures")
    usage_logs: Mapped[List["UsageLog"]] = relationship("UsageLog", back_populates="lecture", cascade="all, delete-orphan")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    lecture_id: Mapped[str] = mapped_column(String(128), ForeignKey("lectures.id", ondelete="CASCADE"), index=True, nullable=False)
    
    stage: Mapped[str] = mapped_column(String(64))  # e.g., 'transcription', 'extract', 'notes', 'assessment'
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="usage_logs")
    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="usage_logs")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # Idempotency key from Lemon Squeezy
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
