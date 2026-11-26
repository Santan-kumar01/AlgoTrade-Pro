from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_DECIMAL_PLACES: int = 8
MAX_DECIMAL_PRECISION: int = 24
MAX_INTEGER_DIGITS: int = MAX_DECIMAL_PRECISION - MAX_DECIMAL_PLACES  # 16


def validate_decimal_precision(value: Decimal) -> Decimal:
    """Validate decimal precision and scale for trading quantities and prices.

    Uses Decimal.as_tuple() and Decimal.adjusted() to inspect coefficient digits
    and exponents without context-sensitive normalization or full integer conversion:
    1. Rejects non-finite values (NaN, Infinity).
    2. Determines meaningful fractional scale by counting and discounting trailing zero
       digits in the coefficient tuple logically, calculating the effective exponent.
       Rejects values with more than 8 meaningful fractional decimal places.
    3. Determines the count of integer (whole) digits using value.adjusted() for non-zero
       values, rejecting values with more than 16 integer digits to ensure compatibility
       with PostgreSQL Numeric(24, 8) columns without overflow.
    4. Handles zero safely.
    5. Returns the original Decimal object unchanged.
    """
    if not value.is_finite():
        raise ValueError("Value must be a finite decimal number.")

    sign, digits, exponent = value.as_tuple()

    # Determine meaningful fractional scale by discounting trailing zeros in coefficient
    if value.is_zero():
        scale = 0
        integer_digits = 0
    else:
        trailing_zeros = 0
        for d in reversed(digits):
            if d == 0:
                trailing_zeros += 1
            else:
                break

        effective_exponent = exponent + trailing_zeros
        scale = -effective_exponent if effective_exponent < 0 else 0

        # Number of integer digits using Decimal.adjusted()
        adj = value.adjusted()
        integer_digits = adj + 1 if adj >= 0 else 0

    if scale > MAX_DECIMAL_PLACES:
        raise ValueError(
            f"Value exceeds maximum allowed scale of {MAX_DECIMAL_PLACES} decimal places."
        )

    if integer_digits > MAX_INTEGER_DIGITS:
        raise ValueError(
            f"Value exceeds maximum allowed whole digits of {MAX_INTEGER_DIGITS} (Numeric(24, 8))."
        )

    return value


class TradeType(str, Enum):
    """Supported trading transaction types."""

    BUY = "BUY"
    SELL = "SELL"


class BuyOrderRequest(BaseModel):
    """Schema representing an incoming request to execute a simulated buy order."""

    asset_id: UUID
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)

    @field_validator("quantity", "price")
    @classmethod
    def validate_decimal_scale_and_precision(cls, v: Decimal) -> Decimal:
        """Enforce maximum scale of 8 decimal places and Numeric(24, 8) compatibility."""
        return validate_decimal_precision(v)


class SellOrderRequest(BaseModel):
    """Schema representing an incoming request to execute a simulated sell order."""

    asset_id: UUID
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)

    @field_validator("quantity", "price")
    @classmethod
    def validate_decimal_scale_and_precision(cls, v: Decimal) -> Decimal:
        """Enforce maximum scale of 8 decimal places and Numeric(24, 8) compatibility."""
        return validate_decimal_precision(v)


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


class TradeHistoryItemResponse(BaseModel):
    """Schema representing an individual trade record in transaction history with asset metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wallet_id: UUID
    asset_id: UUID
    symbol: str
    asset_name: str
    transaction_type: TradeType
    quantity: Decimal
    price: Decimal
    total_amount: Decimal
    currency: str
    created_at: datetime


class TradeHistoryResponse(BaseModel):
    """Paginated trade transaction history response."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    limit: int
    offset: int
    items: list[TradeHistoryItemResponse]
