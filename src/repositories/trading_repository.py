from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Asset, Transaction


class TradingRepository:
    """Database operations for simulated trading."""

    async def get_asset_by_id(
        self,
        asset_id: UUID,
        session: AsyncSession,
    ) -> Asset | None:
        """Retrieve an asset by its ID."""

        statement = select(Asset).where(Asset.id == asset_id)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def get_asset_by_symbol(
        self,
        symbol: str,
        session: AsyncSession,
    ) -> Asset | None:
        """Retrieve an asset by its trading symbol."""

        statement = select(Asset).where(
            func.upper(Asset.symbol) == symbol.upper()
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def get_net_holdings(
        self,
        wallet_id: UUID,
        asset_id: UUID,
        session: AsyncSession,
    ) -> Decimal:
        """Calculate net asset holdings from the transaction ledger."""

        bought_quantity = (
            select(
                func.coalesce(
                    func.sum(Transaction.quantity),
                    Decimal("0"),
                )
            )
            .where(
                Transaction.wallet_id == wallet_id,
                Transaction.asset_id == asset_id,
                Transaction.transaction_type == "BUY",
            )
            .scalar_subquery()
        )

        sold_quantity = (
            select(
                func.coalesce(
                    func.sum(Transaction.quantity),
                    Decimal("0"),
                )
            )
            .where(
                Transaction.wallet_id == wallet_id,
                Transaction.asset_id == asset_id,
                Transaction.transaction_type == "SELL",
            )
            .scalar_subquery()
        )

        statement = select(bought_quantity - sold_quantity)
        result = await session.execute(statement)

        return result.scalar_one() or Decimal("0")

    async def create_transaction(
        self,
        transaction: Transaction,
        session: AsyncSession,
    ) -> Transaction:
        """Stage a transaction in the caller's database transaction."""

        session.add(transaction)
        return transaction
