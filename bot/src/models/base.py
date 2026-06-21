"""SQLAlchemy declarative base and session factory."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.utils.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _register_models() -> None:
    import src.models.order  # noqa: F401
    import src.models.product  # noqa: F401
    import src.models.user  # noqa: F401


async def _migrate_schema() -> None:
    """Add columns introduced after initial deploy (safe to re-run)."""
    statements = [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_address TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee VARCHAR(128)",
        "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS comment TEXT",
    ]
    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))


async def init_db() -> None:
    """Create all tables on startup. Raises on connection or schema errors."""
    _register_models()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await _migrate_schema()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(
            "PostgreSQL ready: %s@%s:%s/%s",
            settings.DB_USER,
            settings.DB_HOST,
            settings.DB_PORT,
            settings.DB_NAME,
        )
    except Exception as error:
        logger.exception(
            "Failed to initialize PostgreSQL (%s@%s:%s/%s): %s",
            settings.DB_USER,
            settings.DB_HOST,
            settings.DB_PORT,
            settings.DB_NAME,
            error,
        )
        raise
