from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import PortfolioSnapshot


class PortfolioSnapshotRepository:
    """Database operations for historical portfolio snapshots."""

    async def create(
        self,
        snapshot: PortfolioSnapshot,
        session: AsyncSession,
    ) -> PortfolioSnapshot:
        """Add a snapshot to the caller-managed transaction."""

        session.add(snapshot)
        await session.flush()
        return snapshot

    async def create_many(
        self,
        snapshots: list[PortfolioSnapshot],
        session: AsyncSession,
    ) -> list[PortfolioSnapshot]:
        """Add multiple currency snapshots atomically."""

        if not snapshots:
            return []

        session.add_all(snapshots)
        await session.flush()
        return snapshots

    async def get_by_id(
        self,
        snapshot_id: UUID,
        wallet_id: UUID,
        session: AsyncSession,
    ) -> PortfolioSnapshot | None:
        """Retrieve a snapshot belonging to the specified wallet."""

        statement = select(PortfolioSnapshot).where(
            PortfolioSnapshot.id == snapshot_id,
            PortfolioSnapshot.wallet_id == wallet_id,
        )

        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_wallet(
        self,
        wallet_id: UUID,
        session: AsyncSession,
        *,
        currency: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PortfolioSnapshot]:
        """Retrieve wallet snapshots with optional filters and pagination."""

        if limit < 1 or limit > 500:
            raise ValueError("Limit must be between 1 and 500.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        if start_at is not None and end_at is not None:
            if start_at > end_at:
                raise ValueError("start_at cannot be after end_at.")

        statement = select(PortfolioSnapshot).where(
            PortfolioSnapshot.wallet_id == wallet_id,
        )

        if currency is not None:
            statement = statement.where(
                PortfolioSnapshot.currency == currency.upper(),
            )

        if start_at is not None:
            statement = statement.where(
                PortfolioSnapshot.snapshot_at >= start_at,
            )

        if end_at is not None:
            statement = statement.where(
                PortfolioSnapshot.snapshot_at <= end_at,
            )

        statement = (
            statement
            .order_by(
                PortfolioSnapshot.snapshot_at.desc(),
                PortfolioSnapshot.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(statement)
        return list(result.scalars().all())
