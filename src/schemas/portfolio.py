from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.schemas.trading import validate_decimal_precision


class PortfolioPositionResponse(BaseModel):
    """Public representation of an individual portfolio position."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    symbol: str
    name: str
    asset_type: str
    currency: str
    quantity: Decimal
    average_cost: Decimal
    total_invested: Decimal
    realized_pnl: Decimal


class PortfolioSummaryResponse(BaseModel):
    """Portfolio summary returned to the authenticated wallet owner."""

    model_config = ConfigDict(from_attributes=True)

    wallet_id: UUID
    positions: tuple[PortfolioPositionResponse, ...]
    realized_pnl_by_currency: dict[str, Decimal]


class MarketPriceInput(BaseModel):
    """Market price supplied for an asset in the portfolio."""

    asset_id: UUID
    market_price: Decimal = Field(gt=0)

    @field_validator("market_price")
    @classmethod
    def validate_market_price(cls, value: Decimal) -> Decimal:
        """Require a finite positive Decimal with supported precision."""
        return validate_decimal_precision(value)


class PortfolioAnalyticsRequest(BaseModel):
    """Request containing market prices for open portfolio positions."""

    market_prices: list[MarketPriceInput]

    @model_validator(mode="after")
    def reject_duplicate_asset_ids(self):
        """Prevent ambiguous prices for the same asset."""
        asset_ids = [item.asset_id for item in self.market_prices]

        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("Duplicate asset IDs are not allowed.")

        return self


class PortfolioPositionAnalyticsResponse(BaseModel):
    """Market valuation and profit/loss for an individual position."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    symbol: str
    currency: str
    quantity: Decimal
    average_cost: Decimal
    total_invested: Decimal
    market_price: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    allocation_percentage: Decimal


class CurrencyAnalyticsResponse(BaseModel):
    """Aggregated portfolio analytics for one currency."""

    model_config = ConfigDict(from_attributes=True)

    currency: str
    total_invested: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal


class PortfolioAnalyticsResponse(BaseModel):
    """Complete portfolio analytics response."""

    model_config = ConfigDict(from_attributes=True)

    wallet_id: UUID
    positions: tuple[PortfolioPositionAnalyticsResponse, ...]
    currencies: tuple[CurrencyAnalyticsResponse, ...]
    concentration_ratio: Decimal | None = None
    concentration_threshold: Decimal = Decimal("50")
    is_concentrated: bool | None = None
    concentrated_positions: tuple[str, ...] = ()


class PortfolioSnapshotResponse(BaseModel):
    """Historical portfolio snapshot returned to the wallet owner."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wallet_id: UUID
    currency: str
    snapshot_at: datetime
    total_invested: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
