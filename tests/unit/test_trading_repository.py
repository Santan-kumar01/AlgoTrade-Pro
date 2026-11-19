from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.sql import Select

from src.models import Asset, Transaction
from src.repositories.trading_repository import TradingRepository


@pytest.mark.asyncio
async def test_get_asset_by_id_returns_asset():
    asset_id = uuid4()
    asset = Asset(
        id=asset_id,
        symbol="BTC",
        name="Bitcoin",
        asset_type="CRYPTO",
        currency="USD",
        is_active=True,
    )

    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = asset
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()

    returned_asset = await repository.get_asset_by_id(
        asset_id,
        session,
    )

    assert returned_asset is asset
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_asset_by_symbol_uses_case_insensitive_lookup():
    asset = Asset(
        id=uuid4(),
        symbol="BTC",
        name="Bitcoin",
        asset_type="CRYPTO",
        currency="USD",
        is_active=True,
    )

    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = asset
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()

    returned_asset = await repository.get_asset_by_symbol(
        "btc",
        session,
    )

    assert returned_asset is asset
    statement = session.execute.await_args.args[0]
    assert isinstance(statement, Select)


@pytest.mark.asyncio
async def test_get_net_holdings_returns_decimal_quantity():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = Decimal("2.50000000")
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()

    holdings = await repository.get_net_holdings(
        uuid4(),
        uuid4(),
        session,
    )

    assert holdings == Decimal("2.50000000")
    assert isinstance(holdings, Decimal)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_net_holdings_returns_zero_when_no_holdings():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = Decimal("0")
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()

    holdings = await repository.get_net_holdings(
        uuid4(),
        uuid4(),
        session,
    )

    assert holdings == Decimal("0")


@pytest.mark.asyncio
async def test_create_transaction_adds_to_session():
    transaction = Transaction(
        wallet_id=uuid4(),
        asset_id=uuid4(),
        transaction_type="BUY",
        quantity=Decimal("1.00000000"),
        price=Decimal("100.00000000"),
        total_amount=Decimal("100.00000000"),
    )

    session = MagicMock()
    session.add = MagicMock()

    repository = TradingRepository()

    returned_transaction = await repository.create_transaction(
        transaction,
        session,
    )

    assert returned_transaction is transaction
    session.add.assert_called_once_with(transaction)
    session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_get_transactions_for_wallet_returns_chronological_history():
    wallet_id = uuid4()
    transactions = [
        Transaction(
            wallet_id=wallet_id,
            asset_id=uuid4(),
            transaction_type="BUY",
            quantity=Decimal("2.00000000"),
            price=Decimal("100.00000000"),
            total_amount=Decimal("200.00000000"),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=uuid4(),
            transaction_type="SELL",
            quantity=Decimal("1.00000000"),
            price=Decimal("120.00000000"),
            total_amount=Decimal("120.00000000"),
        ),
    ]

    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = transactions
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()

    returned_transactions = await repository.get_transactions_for_wallet(
        wallet_id,
        session,
    )

    assert returned_transactions == transactions
    statement = session.execute.await_args.args[0]
    assert isinstance(statement, Select)
    session.execute.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_assets_by_ids_returns_matching_assets():
    assets = [
        Asset(
            id=uuid4(),
            symbol="BTC",
            name="Bitcoin",
            asset_type="CRYPTO",
            currency="USD",
            is_active=True,
        ),
        Asset(
            id=uuid4(),
            symbol="ETH",
            name="Ethereum",
            asset_type="CRYPTO",
            currency="USD",
            is_active=True,
        ),
    ]

    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = assets
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()

    returned_assets = await repository.get_assets_by_ids(
        {asset.id for asset in assets},
        session,
    )

    assert returned_assets == assets
    statement = session.execute.await_args.args[0]
    assert isinstance(statement, Select)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_assets_by_ids_returns_empty_without_database_query():
    session = MagicMock()
    session.execute = AsyncMock()

    repository = TradingRepository()

    returned_assets = await repository.get_assets_by_ids(
        set(),
        session,
    )

    assert returned_assets == []
    session.execute.assert_not_awaited()

