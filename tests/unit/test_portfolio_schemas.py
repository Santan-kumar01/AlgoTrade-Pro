from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.schemas.portfolio import (
    MarketPriceInput,
    PortfolioAnalyticsRequest,
)


def test_market_price_input_accepts_valid_price():
    asset_id = uuid4()

    result = MarketPriceInput(
        asset_id=asset_id,
        market_price=Decimal("125.12345678"),
    )

    assert result.asset_id == asset_id
    assert result.market_price == Decimal("125.12345678")


def test_portfolio_analytics_request_accepts_unique_asset_ids():
    first_asset_id = uuid4()
    second_asset_id = uuid4()

    result = PortfolioAnalyticsRequest(
        market_prices=[
            {"asset_id": first_asset_id, "market_price": "100"},
            {"asset_id": second_asset_id, "market_price": "200"},
        ]
    )

    assert len(result.market_prices) == 2


def test_portfolio_analytics_request_rejects_duplicate_asset_ids():
    asset_id = uuid4()

    with pytest.raises(ValidationError, match="Duplicate asset IDs"):
        PortfolioAnalyticsRequest(
            market_prices=[
                {"asset_id": asset_id, "market_price": "100"},
                {"asset_id": asset_id, "market_price": "150"},
            ]
        )


@pytest.mark.parametrize("invalid_price", ["0", "-10"])
def test_market_price_input_rejects_non_positive_price(invalid_price):
    with pytest.raises(ValidationError):
        MarketPriceInput(
            asset_id=uuid4(),
            market_price=Decimal(invalid_price),
        )


@pytest.mark.parametrize("invalid_price", ["NaN", "Infinity", "-Infinity"])
def test_market_price_input_rejects_non_finite_price(invalid_price):
    with pytest.raises(ValidationError):
        MarketPriceInput(
            asset_id=uuid4(),
            market_price=Decimal(invalid_price),
        )


def test_market_price_input_rejects_excessive_decimal_precision():
    with pytest.raises(ValidationError, match="scale"):
        MarketPriceInput(
            asset_id=uuid4(),
            market_price=Decimal("1.123456789"),
        )
