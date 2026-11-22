from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.services.portfolio_analytics_service import (
    CurrencyAnalytics,
    PortfolioAnalytics,
)
from src.services.portfolio_snapshot_service import (
    PortfolioSnapshotService,
)


@pytest.fixture
def wallet_id():
    return uuid4()


@pytest.fixture
def session():
    return AsyncMock()


@pytest.fixture
def analytics_service():
    return AsyncMock()


@pytest.fixture
def repository():
    return AsyncMock()


@pytest.fixture
def snapshot_service(analytics_service, repository):
    return PortfolioSnapshotService(
        analytics_service=analytics_service,
        repository=repository,
    )


@pytest.mark.asyncio
async def test_create_snapshot_for_multiple_currencies(
    snapshot_service,
    analytics_service,
    repository,
    wallet_id,
    session,
):
    analytics = PortfolioAnalytics(
        wallet_id=wallet_id,
        positions=(),
        currencies=(
            CurrencyAnalytics(
                currency="INR",
                total_invested=Decimal("1000"),
                market_value=Decimal("1200"),
                realized_pnl=Decimal("100"),
                unrealized_pnl=Decimal("100"),
                total_pnl=Decimal("200"),
            ),
            CurrencyAnalytics(
                currency="USD",
                total_invested=Decimal("500"),
                market_value=Decimal("600"),
                realized_pnl=Decimal("50"),
                unrealized_pnl=Decimal("50"),
                total_pnl=Decimal("100"),
            ),
        ),
    )

    analytics_service.get_analytics.return_value = analytics
    repository.create_many.side_effect = lambda snapshots, session: snapshots

    result = await snapshot_service.create_snapshot(
        wallet_id,
        {},
        session,
    )

    assert len(result) == 2
    assert result[0].currency == "INR"
    assert result[1].currency == "USD"

    assert result[0].total_invested == Decimal("1000")
    assert result[0].market_value == Decimal("1200")
    assert result[0].realized_pnl == Decimal("100")
    assert result[0].unrealized_pnl == Decimal("100")
    assert result[0].total_pnl == Decimal("200")

    assert result[1].total_invested == Decimal("500")
    assert result[1].market_value == Decimal("600")
    assert result[1].total_pnl == Decimal("100")

    analytics_service.get_analytics.assert_awaited_once_with(
        wallet_id,
        {},
        session,
    )
    repository.create_many.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_currency_snapshots_share_same_utc_timestamp(
    snapshot_service,
    analytics_service,
    repository,
    wallet_id,
    session,
):
    analytics_service.get_analytics.return_value = PortfolioAnalytics(
        wallet_id=wallet_id,
        positions=(),
        currencies=(
            CurrencyAnalytics(
                currency="INR",
                total_invested=Decimal("100"),
                market_value=Decimal("120"),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("20"),
                total_pnl=Decimal("20"),
            ),
            CurrencyAnalytics(
                currency="USD",
                total_invested=Decimal("200"),
                market_value=Decimal("220"),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("20"),
                total_pnl=Decimal("20"),
            ),
        ),
    )

    repository.create_many.side_effect = lambda snapshots, session: snapshots

    result = await snapshot_service.create_snapshot(
        wallet_id,
        {},
        session,
    )

    assert result[0].snapshot_at == result[1].snapshot_at
    assert result[0].snapshot_at.tzinfo is not None
    assert result[0].snapshot_at.utcoffset().total_seconds() == 0


@pytest.mark.asyncio
async def test_empty_portfolio_returns_empty_list(
    snapshot_service,
    analytics_service,
    repository,
    wallet_id,
    session,
):
    analytics_service.get_analytics.return_value = PortfolioAnalytics(
        wallet_id=wallet_id,
        positions=(),
        currencies=(),
    )

    result = await snapshot_service.create_snapshot(
        wallet_id,
        {},
        session,
    )

    assert result == []
    repository.create_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_analytics_validation_error_is_propagated(
    snapshot_service,
    analytics_service,
    repository,
    wallet_id,
    session,
):
    analytics_service.get_analytics.side_effect = ValueError(
        "Invalid market price."
    )

    with pytest.raises(ValueError, match="Invalid market price"):
        await snapshot_service.create_snapshot(
            wallet_id,
            {},
            session,
        )

    repository.create_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_records_belong_to_requested_wallet(
    snapshot_service,
    analytics_service,
    repository,
    wallet_id,
    session,
):
    analytics_service.get_analytics.return_value = PortfolioAnalytics(
        wallet_id=wallet_id,
        positions=(),
        currencies=(
            CurrencyAnalytics(
                currency="INR",
                total_invested=Decimal("100"),
                market_value=Decimal("150"),
                realized_pnl=Decimal("10"),
                unrealized_pnl=Decimal("40"),
                total_pnl=Decimal("50"),
            ),
        ),
    )

    repository.create_many.side_effect = lambda snapshots, session: snapshots

    result = await snapshot_service.create_snapshot(
        wallet_id,
        {},
        session,
    )

    assert result[0].wallet_id == wallet_id
    assert result[0].currency == "INR"
