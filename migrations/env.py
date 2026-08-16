"""Alembic migration environment for NorAI.

Runs against the SAME async engine config as the app (backend/db/database.py):
* PostgreSQL (Supabase) via asyncpg when DATABASE_URL is set,
* else SQLite via aiosqlite (outputs/norai_main.db) in local dev.

The migration URL is always taken from the app's resolved DATABASE_URL so the
migrations and the runtime app can never drift apart.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Import app Base + all models so autogenerate sees the full metadata.
from backend.db.database import Base, DATABASE_URL, get_engine_kwargs
import backend.db.models  # noqa: F401  (registers tables on Base.metadata)

config = context.config

# When invoked from the running app (backend/db/migrate.py), skip fileConfig:
# alembic.ini's logging config would otherwise replace the app's root handlers
# (e.g. outputs/backend.log) for the rest of the process lifetime.
if config.config_file_name is not None and os.environ.get("NORAI_MIGRATE_NO_LOGGING") != "1":
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return os.environ.get("NORAI_ALEMBIC_URL") or DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Build the engine directly from the app URL instead of
    # async_engine_from_config: ConfigParser %-interpolation would choke on the
    # URL-encoded characters in real DATABASE_URL passwords (e.g. Supabase).
    # Reuse the app's engine kwargs so the Transaction Pooler (port 6543) gets
    # statement_cache_size=0 here too.
    connectable = create_async_engine(
        get_url(), poolclass=pool.NullPool, **get_engine_kwargs(get_url())
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
