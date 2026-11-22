import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class PortfolioSnapshot(Base):
    """Immutable historical portfolio metrics for a wallet and currency."""

    __tablename__ = "portfolio_snapshots"

    __table_args__ = (
        UniqueConstraint(
            "wallet_id",
            "currency",
            "snapshot_at",
            name="uq_portfolio_snapshots_wallet_currency_timestamp",
        ),
        CheckConstraint(
            "length(currency) = 3",
            name="currency_length_valid",
        ),
        CheckConstraint(
            "total_invested >= 0",
            name="total_invested_non_negative",
        ),
        CheckConstraint(
            "market_value >= 0",
            name="market_value_non_negative",
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

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    total_invested: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
    )

    market_value: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
    )

    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
    )

    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
    )

    total_pnl: Mapped[Decimal] = mapped_column(
        Numeric(28, 8),
        nullable=False,
    )