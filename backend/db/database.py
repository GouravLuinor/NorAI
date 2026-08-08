"""
backend/db/database.py

SQLAlchemy 2.0 Async engine and session management for NorAI.
Supports PostgreSQL (Supabase / Production) and fallback to SQLite (local dev).
"""

import os
from typing import AsyncGenerator
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Ensure .env vars (DATABASE_URL, etc.) are loaded when this module is imported standalone.
load_dotenv()

# Base class for ORM models
Base = declarative_base()

# Retrieve database URL from environment or default to local sqlite
DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///outputs/norai_main.db"
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("NORAI_POSTGRES_URL") or DEFAULT_SQLITE_URL

# Adjust postgres driver scheme if provided as postgresql://
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Configure engine kwargs
engine_kwargs = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all registered database tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
