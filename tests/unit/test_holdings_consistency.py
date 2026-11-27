from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql import Select

from src.models import Asset, Transaction
from src.repositories.trading_repository import TradingRepository
from src.services.portfolio_service import PortfolioService


def simulate_sql_net_holdings(
    transactions: list[Transaction],
    wallet_id: UUID,
) -> dict[UUID, Decimal]:
    """Simulate the SQL aggregation of TradingRepository.get_all_net_holdings.

    Replicates:
        SELECT asset_id, SUM(CASE WHEN type='BUY' THEN qty WHEN type='SELL' THEN -qty END)
        WHERE wallet_id = :wallet_id
        GROUP BY asset_id
        HAVING SUM(...) > 0
    """
    totals: dict[UUID, Decimal] = defaultdict(Decimal)
    for tx in transactions:
        if tx.wallet_id != wallet_id:
            continue
        if tx.transaction_type == "BUY":
            totals[tx.asset_id] += tx.quantity
        elif tx.transaction_type == "SELL":
            totals[tx.asset_id] -= tx.quantity

    return {
        asset_id: qty
        for asset_id, qty in totals.items()
        if qty > Decimal("0")
    }


def make_asset(
    symbol: str,
    asset_id: UUID | None = None,
    currency: str = "USD",
) -> Asset:
    """Helper to create an active Asset model instance."""
    return Asset(
        id=asset_id or uuid4(),
        symbol=symbol,
        name=f"{symbol} Token",
        asset_type="CRYPTO",
        currency=currency,
        is_active=True,
    )


def make_tx(
    wallet_id: UUID,
    asset_id: UUID,
    tx_type: str,
    quantity: Decimal,
    price: Decimal,
    created_at: datetime | None = None,
    tx_id: UUID | None = None,
) -> Transaction:
    """Helper to create a valid Transaction instance with exact total_amount."""
    return Transaction(
        id=tx_id or uuid4(),
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type=tx_type,
        quantity=quantity,
        price=price,
        total_amount=quantity * price,
        created_at=created_at or datetime.now(timezone.utc),
    )


# ============================================================================
# Unit 2: SQL vs In-Memory Replay Holdings Consistency Tests
# ============================================================================


@pytest.mark.asyncio
async def test_consistency_multiple_buys_single_asset():
    """Verify SQL net holdings match portfolio replay after multiple BUYs for the same asset."""
    wallet_id = uuid4()
    asset = make_asset("BTC")

    transactions = [
        make_tx(
            wallet_id,
            asset.id,
            "BUY",
            Decimal("2.00000000"),
            Decimal("50000.00000000"),
            datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        ),
        make_tx(
            wallet_id,
            asset.id,
            "BUY",
            Decimal("3.50000000"),
            Decimal("60000.00000000"),
            datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    sql_holdings = simulate_sql_net_holdings(transactions, wallet_id)

    repo = AsyncMock(spec=TradingRepository)
    repo.get_transactions_for_wallet.return_value = transactions
    repo.get_assets_by_ids.return_value = [asset]

    portfolio_service = PortfolioService(repository=repo)
    portfolio = await portfolio_service.get_portfolio(wallet_id, AsyncMock())

    replay_holdings = {pos.asset_id: pos.quantity for pos in portfolio.positions}

    assert sql_holdings == replay_holdings
    assert sql_holdings[asset.id] == Decimal("5.50000000")
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].quantity == Decimal("5.50000000")


@pytest.mark.asyncio
async def test_consistency_partial_sell():
    """Verify SQL net holdings match portfolio replay after partial SELL."""
    wallet_id = uuid4()
    asset = make_asset("ETH")

    transactions = [
        make_tx(
            wallet_id,
            asset.id,
            "BUY",
            Decimal("10.00000000"),
            Decimal("3000.00000000"),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        make_tx(
            wallet_id,
            asset.id,
            "SELL",
            Decimal("4.25000000"),
            Decimal("3500.00000000"),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    ]

    sql_holdings = simulate_sql_net_holdings(transactions, wallet_id)

    repo = AsyncMock(spec=TradingRepository)
    repo.get_transactions_for_wallet.return_value = transactions
    repo.get_assets_by_ids.return_value = [asset]

    portfolio_service = PortfolioService(repository=repo)
    portfolio = await portfolio_service.get_portfolio(wallet_id, AsyncMock())

    replay_holdings = {pos.asset_id: pos.quantity for pos in portfolio.positions}

    assert sql_holdings == replay_holdings
    assert sql_holdings[asset.id] == Decimal("5.75000000")
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].quantity == Decimal("5.75000000")


@pytest.mark.asyncio
async def test_consistency_complete_sell_zero_holdings():
    """Verify completely sold assets are excluded from both SQL holdings and portfolio positions."""
    wallet_id = uuid4()
    asset = make_asset("SOL")

    transactions = [
        make_tx(
            wallet_id,
            asset.id,
            "BUY",
            Decimal("15.00000000"),
            Decimal("100.00000000"),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        make_tx(
            wallet_id,
            asset.id,
            "SELL",
            Decimal("15.00000000"),
            Decimal("120.00000000"),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    ]

    sql_holdings = simulate_sql_net_holdings(transactions, wallet_id)

    repo = AsyncMock(spec=TradingRepository)
    repo.get_transactions_for_wallet.return_value = transactions
    repo.get_assets_by_ids.return_value = [asset]

    portfolio_service = PortfolioService(repository=repo)
    portfolio = await portfolio_service.get_portfolio(wallet_id, AsyncMock())

    replay_holdings = {pos.asset_id: pos.quantity for pos in portfolio.positions}

    # Both must report empty positive holdings
    assert sql_holdings == {}
    assert replay_holdings == {}
    assert len(portfolio.positions) == 0
    # Realized P&L is still tracked in the portfolio summary
    assert portfolio.realized_pnl_by_currency == {"USD": Decimal("300.00000000")}


@pytest.mark.asyncio
async def test_consistency_multiple_assets_mixed_operations():
    """Verify consistency across multiple assets with varied BUY and SELL patterns."""
    wallet_id = uuid4()
    asset_btc = make_asset("BTC")
    asset_eth = make_asset("ETH")
    asset_sol = make_asset("SOL")

    transactions = [
        # BTC: Buy 5, Sell 2 -> Net 3
        make_tx(wallet_id, asset_btc.id, "BUY", Decimal("5"), Decimal("50000"), datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_tx(wallet_id, asset_btc.id, "SELL", Decimal("2"), Decimal("55000"), datetime(2026, 1, 2, tzinfo=timezone.utc)),
        # ETH: Buy 20, Sell 20 -> Net 0 (fully liquidated)
        make_tx(wallet_id, asset_eth.id, "BUY", Decimal("20"), Decimal("3000"), datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_tx(wallet_id, asset_eth.id, "SELL", Decimal("20"), Decimal("3200"), datetime(2026, 1, 3, tzinfo=timezone.utc)),
        # SOL: Buy 100, Buy 50 -> Net 150
        make_tx(wallet_id, asset_sol.id, "BUY", Decimal("100"), Decimal("150"), datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_tx(wallet_id, asset_sol.id, "BUY", Decimal("50"), Decimal("160"), datetime(2026, 1, 4, tzinfo=timezone.utc)),
    ]

    sql_holdings = simulate_sql_net_holdings(transactions, wallet_id)

    repo = AsyncMock(spec=TradingRepository)
    repo.get_transactions_for_wallet.return_value = transactions
    repo.get_assets_by_ids.return_value = [asset_btc, asset_eth, asset_sol]

    portfolio_service = PortfolioService(repository=repo)
    portfolio = await portfolio_service.get_portfolio(wallet_id, AsyncMock())

    replay_holdings = {pos.asset_id: pos.quantity for pos in portfolio.positions}

    assert sql_holdings == replay_holdings
    assert sql_holdings == {
        asset_btc.id: Decimal("3"),
        asset_sol.id: Decimal("150"),
    }
    # Liquidated ETH is not in active positions
    assert asset_eth.id not in sql_holdings
    assert asset_eth.id not in replay_holdings
    assert len(portfolio.positions) == 2


@pytest.mark.asyncio
async def test_consistency_no_transactions_empty_portfolio():
    """Verify empty transaction ledger returns empty holdings across both paths."""
    wallet_id = uuid4()
    transactions = []

    sql_holdings = simulate_sql_net_holdings(transactions, wallet_id)

    repo = AsyncMock(spec=TradingRepository)
    repo.get_transactions_for_wallet.return_value = []
    repo.get_assets_by_ids.return_value = []

    portfolio_service = PortfolioService(repository=repo)
    portfolio = await portfolio_service.get_portfolio(wallet_id, AsyncMock())

    replay_holdings = {pos.asset_id: pos.quantity for pos in portfolio.positions}

    assert sql_holdings == {}
    assert replay_holdings == {}
    assert portfolio.positions == ()


@pytest.mark.asyncio
async def test_consistency_wallet_isolation_multiple_users():
    """Verify transactions from one wallet never leak into another wallet's holdings."""
    wallet_a = uuid4()
    wallet_b = uuid4()
    asset = make_asset("BTC")

    transactions_all = [
        make_tx(wallet_a, asset.id, "BUY", Decimal("10"), Decimal("100")),
        make_tx(wallet_b, asset.id, "BUY", Decimal("25"), Decimal("100")),
        make_tx(wallet_b, asset.id, "SELL", Decimal("10"), Decimal("120")),
    ]

    sql_holdings_a = simulate_sql_net_holdings(transactions_all, wallet_a)
    sql_holdings_b = simulate_sql_net_holdings(transactions_all, wallet_b)

    assert sql_holdings_a == {asset.id: Decimal("10")}
    assert sql_holdings_b == {asset.id: Decimal("15")}

    # Portfolio service receives filtered transactions per wallet from repository
    repo_a = AsyncMock(spec=TradingRepository)
    repo_a.get_transactions_for_wallet.return_value = [
        tx for tx in transactions_all if tx.wallet_id == wallet_a
    ]
    repo_a.get_assets_by_ids.return_value = [asset]

    repo_b = AsyncMock(spec=TradingRepository)
    repo_b.get_transactions_for_wallet.return_value = [
        tx for tx in transactions_all if tx.wallet_id == wallet_b
    ]
    repo_b.get_assets_by_ids.return_value = [asset]

    portfolio_a = await PortfolioService(repository=repo_a).get_portfolio(wallet_a, AsyncMock())
    portfolio_b = await PortfolioService(repository=repo_b).get_portfolio(wallet_b, AsyncMock())

    assert {p.asset_id: p.quantity for p in portfolio_a.positions} == sql_holdings_a
    assert {p.asset_id: p.quantity for p in portfolio_b.positions} == sql_holdings_b


# ============================================================================
# History Filter, Date Boundary, and Deterministic Ordering Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_history_filters_asset_and_transaction_type():
    """Verify repository query statement includes exact asset_id and transaction_type filters."""
    wallet_id = uuid4()
    target_asset_id = uuid4()
    repo = TradingRepository()

    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    await repo.get_transaction_history(
        wallet_id=wallet_id,
        session=session,
        asset_id=target_asset_id,
        transaction_type="buy",
    )

    statement = session.execute.await_args.args[0]
    assert isinstance(statement, Select)
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert f"transactions.asset_id = '{target_asset_id.hex}'" in compiled
    assert "transactions.transaction_type = 'BUY'" in compiled


@pytest.mark.asyncio
async def test_history_date_boundary_filters():
    """Verify repository includes start_at and end_at boundary filters."""
    wallet_id = uuid4()
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    repo = TradingRepository()

    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    await repo.get_transaction_history(
        wallet_id=wallet_id,
        session=session,
        start_at=start,
        end_at=end,
    )

    statement = session.execute.await_args.args[0]
    assert isinstance(statement, Select)
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "transactions.created_at >=" in compiled
    assert "transactions.created_at <=" in compiled


@pytest.mark.asyncio
async def test_history_pagination_deterministic_ordering_with_equal_timestamps():
    """Verify deterministic tie-breaking on id when transactions share identical timestamps."""
    wallet_id = uuid4()
    shared_time = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    repo = TradingRepository()

    session = MagicMock()
    result = MagicMock()
    result.tuples.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    await repo.get_transaction_history(
        wallet_id=wallet_id,
        session=session,
        limit=20,
        offset=10,
    )

    statement = session.execute.await_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    # History uses DESC created_at and DESC id for deterministic reverse-chronological pagination
    assert "ORDER BY transactions.created_at DESC, transactions.id DESC" in compiled
    assert "LIMIT 20" in compiled
    assert "OFFSET 10" in compiled


@pytest.mark.asyncio
async def test_portfolio_replay_same_timestamp_chronological_order():
    """Verify portfolio handles transactions with identical timestamps when ordered validly."""
    wallet_id = uuid4()
    asset = make_asset("BTC")
    same_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # BUY followed by SELL with same created_at
    transactions = [
        make_tx(wallet_id, asset.id, "BUY", Decimal("10"), Decimal("100"), same_time),
        make_tx(wallet_id, asset.id, "SELL", Decimal("5"), Decimal("150"), same_time),
    ]

    repo = AsyncMock(spec=TradingRepository)
    repo.get_transactions_for_wallet.return_value = transactions
    repo.get_assets_by_ids.return_value = [asset]

    portfolio = await PortfolioService(repository=repo).get_portfolio(wallet_id, AsyncMock())

    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].quantity == Decimal("5")
    assert portfolio.positions[0].realized_pnl == Decimal("250")


@pytest.mark.asyncio
async def test_portfolio_replay_sell_exceeding_holdings_raises_value_error():
    """Verify portfolio replay detects illegal sell exceeding cumulative holdings."""
    wallet_id = uuid4()
    asset = make_asset("BTC")

    transactions = [
        make_tx(wallet_id, asset.id, "BUY", Decimal("5"), Decimal("100")),
        make_tx(wallet_id, asset.id, "SELL", Decimal("10"), Decimal("100")),
    ]

    repo = AsyncMock(spec=TradingRepository)
    repo.get_transactions_for_wallet.return_value = transactions
    repo.get_assets_by_ids.return_value = [asset]

    with pytest.raises(
        ValueError,
        match="Sell transaction exceeds available historical holdings.",
    ):
        await PortfolioService(repository=repo).get_portfolio(wallet_id, AsyncMock())


@pytest.mark.asyncio
async def test_portfolio_replay_unsupported_transaction_type_raises_value_error():
    """Verify replay rejects unsupported transaction types with descriptive error."""
    wallet_id = uuid4()
    asset = make_asset("BTC")

    tx = make_tx(wallet_id, asset.id, "DIVIDEND", Decimal("5"), Decimal("100"))

    repo = AsyncMock(spec=TradingRepository)
    repo.get_transactions_for_wallet.return_value = [tx]
    repo.get_assets_by_ids.return_value = [asset]

    with pytest.raises(ValueError, match="Unsupported transaction type: DIVIDEND"):
        await PortfolioService(repository=repo).get_portfolio(wallet_id, AsyncMock())
