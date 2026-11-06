"""Alembic environment configuration for Flood-Risk API.

Reads database connection URL from the DATABASE_URL environment variable so
migrations work identically in development, CI, and production without
hardcoding credentials.

Usage:
    export DATABASE_URL=postgresql+psycopg://flood:flood@localhost:5432/flooddb
    alembic upgrade head
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object (gives access to alembic.ini values)
config = context.config

# Standard Python logging setup from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No SQLAlchemy ORM models are used (raw psycopg) so target_metadata stays None.
# Migrations are written manually from infra/postgres/init.sql.
target_metadata = None


def _get_url() -> str:
    """Return the database URL, preferring DATABASE_URL env var over alembic.ini."""
    url = os.environ.get("DATABASE_URL", "")
    if url:
        # psycopg3 uses postgresql+psycopg:// scheme; normalise if bare postgresql:// given
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    # Fallback to alembic.ini value (may be blank — migrations will fail with a clear error)
    ini_url = config.get_main_option("sqlalchemy.url", "")
    if not ini_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Export DATABASE_URL=postgresql+psycopg://user:pass@host/db before running alembic."
        )
    return ini_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live connection)."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live PostgreSQL database."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
