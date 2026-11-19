import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import settings


@pytest.fixture
async def db_engine():
    """Create an isolated engine for the dedicated test database."""
    if not settings.test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must be configured before running "
            "integration tests."
        )

    test_engine = create_async_engine(
        settings.test_database_url,
        poolclass=NullPool,
    )

    try:
        async with test_engine.connect() as connection:
            result = await connection.execute(
                text("SELECT current_database()")
            )
            database_name = result.scalar_one()

            if database_name != "algotrade_pro_test":
                raise RuntimeError(
                    "Integration tests require algotrade_pro_test. "
                    f"Connected database: {database_name}"
                )

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
    """Verify the dedicated integration test database."""
    async with db_engine.connect() as connection:
        result = await connection.execute(
            text("SELECT current_database()")
        )
        assert result.scalar_one() == "algotrade_pro_test"
