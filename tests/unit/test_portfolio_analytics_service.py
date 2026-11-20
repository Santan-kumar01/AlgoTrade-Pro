from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.services.portfolio_analytics_service import (
    MarketPriceValidationError,
    PortfolioAnalyticsService,
)
from src.services.portfolio_service import (
    PortfolioPosition,
    PortfolioSummary,
)


@pytest.mark.asyncio
async def test_analytics_calculates_market_value_and_profit():
    wallet_id = uuid4()
    asset_id = uuid4()

    portfolio = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(
            PortfolioPosition(
                asset_id=asset_id,
                symbol="BTC",
                name="Bitcoin",
                asset_type="CRYPTO",
                currency="USD",
                quantity=Decimal("2"),
                average_cost=Decimal("100"),
                total_invested=Decimal("200"),
                realized_pnl=Decimal("20"),
            ),
        ),
        realized_pnl_by_currency={"USD": Decimal("20")},
    )

    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = portfolio

    service = PortfolioAnalyticsService(portfolio_service)

    result = await service.get_analytics(
        wallet_id,
        {asset_id: Decimal("150")},
        AsyncMock(),
    )

    position = result.positions[0]
    currency = result.currencies[0]

    assert position.market_value == Decimal("300")
    assert position.unrealized_pnl == Decimal("100")
    assert position.realized_pnl == Decimal("20")
    assert position.total_pnl == Decimal("120")
    assert position.allocation_percentage == Decimal("100")

    assert currency.total_invested == Decimal("200")
    assert currency.market_value == Decimal("300")
    assert currency.total_pnl == Decimal("120")


@pytest.mark.asyncio
async def test_analytics_calculates_allocation_by_currency():
    wallet_id = uuid4()
    first_asset_id = uuid4()
    second_asset_id = uuid4()

    positions = (
        PortfolioPosition(
            asset_id=first_asset_id,
            symbol="BTC",
            name="Bitcoin",
            asset_type="CRYPTO",
            currency="USD",
            quantity=Decimal("2"),
            average_cost=Decimal("100"),
            total_invested=Decimal("200"),
            realized_pnl=Decimal("0"),
        ),
        PortfolioPosition(
            asset_id=second_asset_id,
            symbol="ETH",
            name="Ethereum",
            asset_type="CRYPTO",
            currency="USD",
            quantity=Decimal("2"),
            average_cost=Decimal("50"),
            total_invested=Decimal("100"),
            realized_pnl=Decimal("0"),
        ),
    )

    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = PortfolioSummary(
        wallet_id=wallet_id,
        positions=positions,
        realized_pnl_by_currency={"USD": Decimal("0")},
    )

    service = PortfolioAnalyticsService(portfolio_service)

    result = await service.get_analytics(
        wallet_id,
        {
            first_asset_id: Decimal("100"),
            second_asset_id: Decimal("50"),
        },
        AsyncMock(),
    )

    by_symbol = {position.symbol: position for position in result.positions}

    assert by_symbol["BTC"].allocation_percentage == Decimal("66.6666666666666666666666666666666666666666666666666666666667")
    assert by_symbol["ETH"].allocation_percentage == Decimal("33.3333333333333333333333333333333333333333333333333333333333")


@pytest.mark.asyncio
async def test_analytics_rejects_missing_market_price():
    wallet_id = uuid4()
    asset_id = uuid4()

    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(
            PortfolioPosition(
                asset_id=asset_id,
                symbol="BTC",
                name="Bitcoin",
                asset_type="CRYPTO",
                currency="USD",
                quantity=Decimal("1"),
                average_cost=Decimal("100"),
                total_invested=Decimal("100"),
                realized_pnl=Decimal("0"),
            ),
        ),
        realized_pnl_by_currency={"USD": Decimal("0")},
    )

    service = PortfolioAnalyticsService(portfolio_service)

    with pytest.raises(MarketPriceValidationError, match="Market prices missing"):
        await service.get_analytics(wallet_id, {}, AsyncMock())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_price",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
async def test_analytics_rejects_invalid_market_price(invalid_price):
    wallet_id = uuid4()
    asset_id = uuid4()

    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(
            PortfolioPosition(
                asset_id=asset_id,
                symbol="BTC",
                name="Bitcoin",
                asset_type="CRYPTO",
                currency="USD",
                quantity=Decimal("1"),
                average_cost=Decimal("100"),
                total_invested=Decimal("100"),
                realized_pnl=Decimal("0"),
            ),
        ),
        realized_pnl_by_currency={"USD": Decimal("0")},
    )

    service = PortfolioAnalyticsService(portfolio_service)

    with pytest.raises(MarketPriceValidationError, match="Market price"):
        await service.get_analytics(
            wallet_id,
            {asset_id: invalid_price},
            AsyncMock(),
        )

@pytest.mark.asyncio
async def test_analytics_rejects_unknown_asset_market_price():
    wallet_id = uuid4()
    unknown_asset_id = uuid4()

    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(),
        realized_pnl_by_currency={},
    )

    service = PortfolioAnalyticsService(portfolio_service)

    with pytest.raises(MarketPriceValidationError, match="unknown asset IDs"):
        await service.get_analytics(
            wallet_id,
            {unknown_asset_id: Decimal("100")},
            AsyncMock(),
        )

@pytest.mark.asyncio
async def test_analytics_keeps_currency_allocations_separate():
    wallet_id = uuid4()
    btc_id = uuid4()
    gold_id = uuid4()

    positions = (
        PortfolioPosition(
            asset_id=btc_id,
            symbol="BTC",
            name="Bitcoin",
            asset_type="CRYPTO",
            currency="USD",
            quantity=Decimal("2"),
            average_cost=Decimal("100"),
            total_invested=Decimal("200"),
            realized_pnl=Decimal("0"),
        ),
        PortfolioPosition(
            asset_id=gold_id,
            symbol="GOLD",
            name="Gold",
            asset_type="COMMODITY",
            currency="INR",
            quantity=Decimal("2"),
            average_cost=Decimal("5000"),
            total_invested=Decimal("10000"),
            realized_pnl=Decimal("0"),
        ),
    )

    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = PortfolioSummary(
        wallet_id=wallet_id,
        positions=positions,
        realized_pnl_by_currency={
            "USD": Decimal("0"),
            "INR": Decimal("0"),
        },
    )

    service = PortfolioAnalyticsService(portfolio_service)

    result = await service.get_analytics(
        wallet_id,
        {
            btc_id: Decimal("150"),
            gold_id: Decimal("6000"),
        },
        AsyncMock(),
    )

    by_symbol = {position.symbol: position for position in result.positions}
    by_currency = {
        currency.currency: currency for currency in result.currencies
    }

    assert by_symbol["BTC"].market_value == Decimal("300")
    assert by_symbol["BTC"].allocation_percentage == Decimal("100")

    assert by_symbol["GOLD"].market_value == Decimal("12000")
    assert by_symbol["GOLD"].allocation_percentage == Decimal("100")

    assert by_currency["USD"].market_value == Decimal("300")
    assert by_currency["INR"].market_value == Decimal("12000")



@pytest.mark.asyncio
async def test_analytics_handles_empty_portfolio():
    wallet_id = uuid4()
    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(),
        realized_pnl_by_currency={},
    )

    service = PortfolioAnalyticsService(portfolio_service)

    result = await service.get_analytics(wallet_id, {}, AsyncMock())

    assert result.wallet_id == wallet_id
    assert result.positions == ()
    assert result.currencies == ()


@pytest.mark.asyncio
async def test_analytics_preserves_realized_pnl_without_open_positions():
    wallet_id = uuid4()
    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(),
        realized_pnl_by_currency={"USD": Decimal("75")},
    )

    service = PortfolioAnalyticsService(portfolio_service)

    result = await service.get_analytics(wallet_id, {}, AsyncMock())

    currency = result.currencies[0]
    assert currency.currency == "USD"
    assert currency.total_invested == Decimal("0")
    assert currency.market_value == Decimal("0")
    assert currency.realized_pnl == Decimal("75")
    assert currency.unrealized_pnl == Decimal("0")
    assert currency.total_pnl == Decimal("75")


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_price", [100, 100.5])
async def test_analytics_rejects_non_decimal_market_price(invalid_price):
    wallet_id = uuid4()
    asset_id = uuid4()
    portfolio_service = AsyncMock()
    portfolio_service.get_portfolio.return_value = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(
            PortfolioPosition(
                asset_id=asset_id,
                symbol="BTC",
                name="Bitcoin",
                asset_type="CRYPTO",
                currency="USD",
                quantity=Decimal("1"),
                average_cost=Decimal("100"),
                total_invested=Decimal("100"),
                realized_pnl=Decimal("0"),
            ),
        ),
        realized_pnl_by_currency={"USD": Decimal("0")},
    )

    service = PortfolioAnalyticsService(portfolio_service)

    with pytest.raises(MarketPriceValidationError, match="finite Decimal"):
        await service.get_analytics(
            wallet_id,
            {asset_id: invalid_price},
            AsyncMock(),
        )


@pytest.mark.asyncio
async def test_analytics_rejects_non_dictionary_market_prices():
    wallet_id = uuid4()
    portfolio_service = AsyncMock()
    service = PortfolioAnalyticsService(portfolio_service)

    with pytest.raises(
        MarketPriceValidationError,
        match="dictionary",
    ):
        await service.get_analytics(wallet_id, [], AsyncMock())

    portfolio_service.get_portfolio.assert_not_awaited() 
