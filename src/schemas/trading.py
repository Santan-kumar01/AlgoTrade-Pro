from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class BuyOrderRequest(BaseModel):
    """Schema representing an incoming request to execute a simulated buy order."""

    asset_id: UUID
    quantity: Decimal
    price: Decimal


class SellOrderRequest(BaseModel):
    """Schema representing an incoming request to execute a simulated sell order."""

    asset_id: UUID
    quantity: Decimal
    price: Decimal
