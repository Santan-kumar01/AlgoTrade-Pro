import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import settings


@pytest.fixture
async def db_engine():
    """Create an isolated database engine for each test."""
    test_engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
    )

    try:
        yield test_engine
    finally:
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_connection(db_engine: AsyncEngine):
    """Verify a real connection to PostgreSQL."""
    async with db_engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_database_name(db_engine: AsyncEngine):
    """Verify the active database name."""
    async with db_engine.connect() as connection:
        result = await connection.execute(
            text("SELECT current_database()")
        )
        assert result.scalar_one() == "algotrade_pro"
