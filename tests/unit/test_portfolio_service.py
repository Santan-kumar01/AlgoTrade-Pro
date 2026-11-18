from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.models import Asset, Transaction
from src.services.portfolio_service import PortfolioService


@pytest.mark.asyncio
async def test_portfolio_calculates_position_after_buy():
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
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type="BUY",
        quantity=Decimal("2.00000000"),
        price=Decimal("100.00000000"),
        total_amount=Decimal("200.00000000"),
        created_at=datetime.now(timezone.utc),
    )

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = [transaction]
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    portfolio = await service.get_portfolio(wallet_id, AsyncMock())

    assert len(portfolio.positions) == 1

    position = portfolio.positions[0]
    assert position.symbol == "BTC"
    assert position.quantity == Decimal("2.00000000")
    assert position.average_cost == Decimal("100.00000000")
    assert position.total_invested == Decimal("200.00000000")
    assert position.realized_pnl == Decimal("0")
    assert portfolio.realized_pnl_by_currency == {"USD": Decimal("0")}

@pytest.mark.asyncio
async def test_portfolio_calculates_weighted_average_and_partial_sell_profit():
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

    transactions = [
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("100"),
            total_amount=Decimal("200"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("200"),
            total_amount=Decimal("400"),
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="SELL",
            quantity=Decimal("1"),
            price=Decimal("250"),
            total_amount=Decimal("250"),
            created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        ),
    ]

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = transactions
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    portfolio = await service.get_portfolio(wallet_id, AsyncMock())

    assert len(portfolio.positions) == 1

    position = portfolio.positions[0]

    assert position.quantity == Decimal("3")
    assert position.average_cost == Decimal("150")
    assert position.total_invested == Decimal("450")
    assert position.realized_pnl == Decimal("100")
    assert portfolio.realized_pnl_by_currency == {"USD": Decimal("100")}

@pytest.mark.asyncio
async def test_portfolio_calculates_realized_loss_after_sell():
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

    transactions = [
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("100"),
            total_amount=Decimal("200"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="SELL",
            quantity=Decimal("1"),
            price=Decimal("80"),
            total_amount=Decimal("80"),
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    ]

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = transactions
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    portfolio = await service.get_portfolio(wallet_id, AsyncMock())

    position = portfolio.positions[0]

    assert position.quantity == Decimal("1")
    assert position.average_cost == Decimal("100")
    assert position.total_invested == Decimal("100")
    assert position.realized_pnl == Decimal("-20")
    assert portfolio.realized_pnl_by_currency == {"USD": Decimal("-20")}

@pytest.mark.asyncio
async def test_portfolio_excludes_fully_closed_position():
    wallet_id = uuid4()
    asset_id = uuid4()

    transactions = [
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("100"),
            total_amount=Decimal("200"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="SELL",
            quantity=Decimal("2"),
            price=Decimal("120"),
            total_amount=Decimal("240"),
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    ]

    asset = Asset(
        id=asset_id,
        symbol="BTC",
        name="Bitcoin",
        asset_type="CRYPTO",
        currency="USD",
        is_active=True,
    )

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = transactions
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    portfolio = await service.get_portfolio(wallet_id, AsyncMock())

    assert portfolio.positions == ()
    assert portfolio.realized_pnl_by_currency == {"USD": Decimal("40")}
    repository.get_assets_by_ids.assert_awaited_once()

@pytest.mark.asyncio
async def test_portfolio_rejects_sell_exceeding_available_holdings():
    wallet_id = uuid4()
    asset_id = uuid4()

    transactions = [
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("100"),
            total_amount=Decimal("200"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=asset_id,
            transaction_type="SELL",
            quantity=Decimal("3"),
            price=Decimal("120"),
            total_amount=Decimal("360"),
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    ]

    asset = Asset(
        id=asset_id,
        symbol="BTC",
        name="Bitcoin",
        asset_type="CRYPTO",
        currency="USD",
        is_active=True,
    )

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = transactions
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    with pytest.raises(
        ValueError,
        match="Sell transaction exceeds available historical holdings.",
    ):
        await service.get_portfolio(wallet_id, AsyncMock())

    repository.get_assets_by_ids.assert_awaited_once()


@pytest.mark.asyncio
async def test_portfolio_keeps_realized_pnl_separate_by_currency():
    wallet_id = uuid4()
    usd_asset_id = uuid4()
    inr_asset_id = uuid4()

    assets = [
        Asset(
            id=usd_asset_id,
            symbol="BTC",
            name="Bitcoin",
            asset_type="CRYPTO",
            currency="USD",
            is_active=True,
        ),
        Asset(
            id=inr_asset_id,
            symbol="ETH",
            name="Ethereum",
            asset_type="CRYPTO",
            currency="INR",
            is_active=True,
        ),
    ]

    transactions = [
        Transaction(
            wallet_id=wallet_id,
            asset_id=usd_asset_id,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("100"),
            total_amount=Decimal("200"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=usd_asset_id,
            transaction_type="SELL",
            quantity=Decimal("1"),
            price=Decimal("150"),
            total_amount=Decimal("150"),
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=inr_asset_id,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("1000"),
            total_amount=Decimal("2000"),
            created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        ),
        Transaction(
            wallet_id=wallet_id,
            asset_id=inr_asset_id,
            transaction_type="SELL",
            quantity=Decimal("1"),
            price=Decimal("900"),
            total_amount=Decimal("900"),
            created_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        ),
    ]

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = transactions
    repository.get_assets_by_ids.return_value = assets

    service = PortfolioService(repository=repository)
    portfolio = await service.get_portfolio(wallet_id, AsyncMock())

    assert portfolio.realized_pnl_by_currency == {
        "USD": Decimal("50"),
        "INR": Decimal("-100"),
    }
    assert len(portfolio.positions) == 2
    repository.get_assets_by_ids.assert_awaited_once()


@pytest.mark.asyncio
async def test_portfolio_rejects_non_finite_transaction_quantity():
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
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type="BUY",
        quantity=Decimal("NaN"),
        price=Decimal("100"),
        total_amount=Decimal("200"),
        created_at=datetime.now(timezone.utc),
    )

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = [transaction]
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    with pytest.raises(
        ValueError,
        match="Transaction quantity must be a finite Decimal.",
    ):
        await service.get_portfolio(wallet_id, AsyncMock())


@pytest.mark.asyncio
async def test_portfolio_rejects_mismatched_transaction_total():
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
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type="BUY",
        quantity=Decimal("2"),
        price=Decimal("100"),
        total_amount=Decimal("250"),
        created_at=datetime.now(timezone.utc),
    )

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = [transaction]
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    with pytest.raises(
        ValueError,
        match="Transaction total_amount must equal quantity multiplied by price.",
    ):
        await service.get_portfolio(wallet_id, AsyncMock())


@pytest.mark.asyncio
async def test_portfolio_rejects_missing_asset_metadata():
    wallet_id = uuid4()
    asset_id = uuid4()

    transaction = Transaction(
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type="BUY",
        quantity=Decimal("1"),
        price=Decimal("100"),
        total_amount=Decimal("100"),
        created_at=datetime.now(timezone.utc),
    )

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = [transaction]
    repository.get_assets_by_ids.return_value = []

    service = PortfolioService(repository=repository)

    with pytest.raises(
        ValueError,
        match="Asset metadata not found for asset IDs:",
    ):
        await service.get_portfolio(wallet_id, AsyncMock())

    repository.get_assets_by_ids.assert_awaited_once()

@pytest.mark.asyncio
async def test_portfolio_accepts_trailing_decimal_zeros():
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
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type="BUY",
        quantity=Decimal("1.000000000"),
        price=Decimal("100.000000000"),
        total_amount=Decimal("100.000000000"),
        created_at=datetime.now(timezone.utc),
    )

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = [transaction]
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    portfolio = await service.get_portfolio(wallet_id, AsyncMock())

    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].quantity == Decimal("1.000000000")
    assert portfolio.positions[0].total_invested == Decimal("100.000000000")


@pytest.mark.asyncio
async def test_portfolio_rejects_sell_without_historical_buy():
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
        wallet_id=wallet_id,
        asset_id=asset_id,
        transaction_type="SELL",
        quantity=Decimal("1"),
        price=Decimal("100"),
        total_amount=Decimal("100"),
        created_at=datetime.now(timezone.utc),
    )

    repository = AsyncMock()
    repository.get_transactions_for_wallet.return_value = [transaction]
    repository.get_assets_by_ids.return_value = [asset]

    service = PortfolioService(repository=repository)

    with pytest.raises(
        ValueError,
        match="Sell transaction exceeds available historical holdings.",
    ):
        await service.get_portfolio(wallet_id, AsyncMock())
