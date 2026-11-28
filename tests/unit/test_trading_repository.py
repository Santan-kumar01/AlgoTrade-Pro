from datetime import datetime, timezone
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


@pytest.mark.asyncio
async def test_get_transaction_history_with_filters_and_pagination():
    wallet_id = uuid4()
    asset_id = uuid4()
    asset = Asset(
        id=asset_id,
        symbol="AAPL",
        name="Apple Inc.",
        asset_type="STOCK",
        currency="USD",
        is_active=True,
    )
    transaction = Transaction(
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type="BUY",
        quantity=Decimal("10.00000000"),
        price=Decimal("150.00000000"),
        total_amount=Decimal("1500.00000000"),
    )

    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.all.return_value = [(transaction, asset)]
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()
    rows = await repository.get_transaction_history(
        wallet_id=wallet_id,
        session=session,
        asset_id=asset_id,
        transaction_type="BUY",
        limit=10,
        offset=0,
    )

    assert len(rows) == 1
    assert rows[0] == (transaction, asset)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_transaction_history_with_filters():
    wallet_id = uuid4()
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = 42
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()
    count = await repository.count_transaction_history(
        wallet_id=wallet_id,
        session=session,
        transaction_type="SELL",
    )

    assert count == 42
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_transaction_by_id_returns_matching_row():
    tx_id = uuid4()
    wallet_id = uuid4()
    asset_id = uuid4()
    asset = Asset(
        id=asset_id,
        symbol="BTC",
        name="Bitcoin",
        asset_type="CRYPTO",
        currency="USD",
        is_active=True,
    )
    transaction = Transaction(
        id=tx_id,
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type="BUY",
        quantity=Decimal("1.00000000"),
        price=Decimal("50000.00000000"),
        total_amount=Decimal("50000.00000000"),
    )

    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.first.return_value = (transaction, asset)
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()
    row = await repository.get_transaction_by_id(
        transaction_id=tx_id,
        wallet_id=wallet_id,
        session=session,
    )

    assert row == (transaction, asset)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_transaction_by_id_returns_none_when_not_found():
    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()
    row = await repository.get_transaction_by_id(
        transaction_id=uuid4(),
        wallet_id=uuid4(),
        session=session,
    )

    assert row is None
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_all_net_holdings_aggregates_positive_balances():
    wallet_id = uuid4()
    asset1_id = uuid4()
    asset2_id = uuid4()

    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.all.return_value = [
        (asset1_id, Decimal("10.00000000")),
        (asset2_id, Decimal("5.50000000")),
    ]
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()
    holdings = await repository.get_all_net_holdings(wallet_id, session)

    assert holdings == {
        asset1_id: Decimal("10.00000000"),
        asset2_id: Decimal("5.50000000"),
    }
    session.execute.assert_awaited_once()


# ============================================================================
# Phase 6: Regression & Boundary Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_all_net_holdings_empty_returns_empty_dict():
    """Verify get_all_net_holdings returns empty dict when query returns no rows."""
    wallet_id = uuid4()
    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()
    holdings = await repository.get_all_net_holdings(wallet_id, session)

    assert holdings == {}
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_transaction_history_with_identical_start_and_end_at():
    """Verify get_transaction_history builds query with identical start_at and end_at."""
    wallet_id = uuid4()
    point_in_time = datetime(2026, 2, 10, 15, 30, 0, tzinfo=timezone.utc)
    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    repository = TradingRepository()
    await repository.get_transaction_history(
        wallet_id=wallet_id,
        session=session,
        start_at=point_in_time,
        end_at=point_in_time,
    )

    statement = session.execute.await_args.args[0]
    assert isinstance(statement, Select)
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "transactions.created_at >=" in compiled
    assert "transactions.created_at <=" in compiled

