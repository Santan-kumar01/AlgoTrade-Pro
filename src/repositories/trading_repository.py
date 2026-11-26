from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
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

    async def get_assets_by_ids(
        self,
        asset_ids: set[UUID],
        session: AsyncSession,
    ) -> list[Asset]:
        """Retrieve multiple assets in a single database query."""

        if not asset_ids:
            return []

        statement = select(Asset).where(Asset.id.in_(asset_ids))
        result = await session.execute(statement)
        return list(result.scalars().all())

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

    async def get_transactions_for_wallet(
        self,
        wallet_id: UUID,
        session: AsyncSession,
    ) -> list[Transaction]:
        """Retrieve wallet transactions in chronological order."""

        statement = (
            select(Transaction)
            .where(Transaction.wallet_id == wallet_id)
            .order_by(
                Transaction.created_at.asc(),
                Transaction.id.asc(),
            )
        )

        result = await session.execute(statement)
        return list(result.scalars().all())

    async def get_transaction_history(
        self,
        wallet_id: UUID,
        session: AsyncSession,
        *,
        asset_id: UUID | None = None,
        transaction_type: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[Transaction, Asset]]:
        """Retrieve paginated transaction records joined with asset details in descending order."""
        statement = (
            select(Transaction, Asset)
            .join(Asset, Transaction.asset_id == Asset.id)
            .where(Transaction.wallet_id == wallet_id)
        )

        if asset_id is not None:
            statement = statement.where(Transaction.asset_id == asset_id)

        if transaction_type is not None:
            statement = statement.where(
                Transaction.transaction_type == transaction_type.upper()
            )

        if start_at is not None:
            statement = statement.where(Transaction.created_at >= start_at)

        if end_at is not None:
            statement = statement.where(Transaction.created_at <= end_at)

        statement = (
            statement.order_by(
                Transaction.created_at.desc(),
                Transaction.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(statement)
        return list(result.tuples().all())

    async def count_transaction_history(
        self,
        wallet_id: UUID,
        session: AsyncSession,
        *,
        asset_id: UUID | None = None,
        transaction_type: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> int:
        """Count total transactions matching the specified criteria for pagination."""
        statement = (
            select(func.count(Transaction.id))
            .where(Transaction.wallet_id == wallet_id)
        )

        if asset_id is not None:
            statement = statement.where(Transaction.asset_id == asset_id)

        if transaction_type is not None:
            statement = statement.where(
                Transaction.transaction_type == transaction_type.upper()
            )

        if start_at is not None:
            statement = statement.where(Transaction.created_at >= start_at)

        if end_at is not None:
            statement = statement.where(Transaction.created_at <= end_at)

        result = await session.execute(statement)
        return result.scalar_one() or 0

    async def get_transaction_by_id(
        self,
        transaction_id: UUID,
        wallet_id: UUID,
        session: AsyncSession,
    ) -> tuple[Transaction, Asset] | None:
        """Retrieve a single transaction with its asset metadata by ID and wallet ID."""
        statement = (
            select(Transaction, Asset)
            .join(Asset, Transaction.asset_id == Asset.id)
            .where(
                Transaction.id == transaction_id,
                Transaction.wallet_id == wallet_id,
            )
        )
        result = await session.execute(statement)
        row = result.tuples().first()
        return row if row is not None else None

    async def get_all_net_holdings(
        self,
        wallet_id: UUID,
        session: AsyncSession,
    ) -> dict[UUID, Decimal]:
        """Aggregate net positive holdings across all assets for a wallet in SQL."""
        statement = (
            select(
                Transaction.asset_id,
                func.sum(
                    case(
                        (Transaction.transaction_type == "BUY", Transaction.quantity),
                        (Transaction.transaction_type == "SELL", -Transaction.quantity),
                        else_=Decimal("0"),
                    )
                ).label("net_quantity"),
            )
            .where(Transaction.wallet_id == wallet_id)
            .group_by(Transaction.asset_id)
            .having(
                func.sum(
                    case(
                        (Transaction.transaction_type == "BUY", Transaction.quantity),
                        (Transaction.transaction_type == "SELL", -Transaction.quantity),
                        else_=Decimal("0"),
                    )
                ) > Decimal("0")
            )
        )
        result = await session.execute(statement)
        return {asset_id: net_qty for asset_id, net_qty in result.tuples().all()}
