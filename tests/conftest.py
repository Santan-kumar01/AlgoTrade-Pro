from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.core.config import settings
from src.models import Asset, Transaction, User, Wallet


TEST_DATABASE_NAME = "algotrade_pro_test"


@pytest.fixture
async def db_engine():
    """Create an engine restricted to the dedicated test database."""
    if not settings.test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must be configured before running "
            "integration tests."
        )

    engine = create_async_engine(
        settings.test_database_url,
        poolclass=NullPool,
    )

    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT current_database()")
            )
            database_name = result.scalar_one()

            if database_name != TEST_DATABASE_NAME:
                raise RuntimeError(
                    f"Expected {TEST_DATABASE_NAME}, "
                    f"connected to {database_name}. "
                    "Refusing to run integration tests."
                )

        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine):
    """Provide independent sessions for integration tests."""
    return async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def trading_user(
    db_session_factory,
) -> AsyncIterator[tuple[User, Wallet]]:
    """Create a unique user and wallet for a trading test."""
    user_id = uuid4()
    wallet_id = None

    async with db_session_factory() as session:
        user = User(
            id=user_id,
            email=f"{user_id.hex}@integration.test",
            password_hash="integration-test-hash",
        )
        wallet = Wallet(
            user_id=user_id,
            balance=Decimal("10000.00000000"),
            currency="USD",
        )

        session.add_all([user, wallet])
        await session.commit()
        await session.refresh(user)
        await session.refresh(wallet)
        wallet_id = wallet.id

    try:
        yield user, wallet
    finally:
        async with db_session_factory() as cleanup_session:
            await cleanup_session.execute(
                delete(Transaction).where(
                    Transaction.wallet_id == wallet_id
                )
            )
            await cleanup_session.execute(
                delete(Wallet).where(Wallet.id == wallet_id)
            )
            await cleanup_session.execute(
                delete(User).where(User.id == user_id)
            )
            await cleanup_session.commit()


@pytest.fixture
async def trading_asset(
    db_session_factory,
) -> AsyncIterator[Asset]:
    """Create a unique active USD asset for a trading test."""
    asset_id = uuid4()

    async with db_session_factory() as session:
        asset = Asset(
            id=asset_id,
            symbol=f"TST{asset_id.hex[:8].upper()}",
            name="Integration Test Asset",
            asset_type="STOCK",
            currency="USD",
            is_active=True,
        )

        session.add(asset)
        await session.commit()
        await session.refresh(asset)

    try:
        yield asset
    finally:
        async with db_session_factory() as cleanup_session:
            await cleanup_session.execute(
                delete(Transaction).where(
                    Transaction.asset_id == asset_id
                )
            )
            await cleanup_session.execute(
                delete(Asset).where(Asset.id == asset_id)
            )
            await cleanup_session.commit()
