from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
