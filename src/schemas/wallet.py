from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WalletResponse(BaseModel):
    """Public wallet information returned to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    balance: Decimal
    currency: str
