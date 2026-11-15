from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TradeType(str, Enum):
    """Supported trading transaction types."""

    BUY = "BUY"
    SELL = "SELL"


class BuyOrderRequest(BaseModel):
    """Schema representing an incoming request to execute a simulated buy order."""

    asset_id: UUID
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)


class SellOrderRequest(BaseModel):
    """Schema representing an incoming request to execute a simulated sell order."""

    asset_id: UUID
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)


class TradeResponse(BaseModel):
    """Schema representing an executed trade transaction response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wallet_id: UUID
    asset_id: UUID
    transaction_type: TradeType
    quantity: Decimal
    price: Decimal
    total_amount: Decimal
    created_at: datetime
