import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Transaction(Base):
    """Append-only record of a simulated trading transaction."""

    __tablename__ = "transactions"

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('BUY', 'SELL')",
            name="valid_transaction_type",
        ),
        CheckConstraint(
            "quantity > 0",
            name="quantity_positive",
        ),
        CheckConstraint(
            "price > 0",
            name="price_positive",
        ),
        CheckConstraint(
            "total_amount > 0",
            name="total_amount_positive",
        ),
        CheckConstraint(
            "total_amount = quantity * price",
            name="total_amount_matches_quantity_price",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(4),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

