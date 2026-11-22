from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import PortfolioSnapshot
from src.repositories.portfolio_snapshot_repository import (
    PortfolioSnapshotRepository,
)
from src.services.portfolio_analytics_service import (
    PortfolioAnalytics,
    PortfolioAnalyticsService,
)


class PortfolioSnapshotService:
    """Create immutable, currency-wise historical portfolio snapshots."""

    def __init__(
        self,
        analytics_service: PortfolioAnalyticsService | None = None,
        repository: PortfolioSnapshotRepository | None = None,
    ) -> None:
        self.analytics_service = (
            analytics_service
            if analytics_service is not None
            else PortfolioAnalyticsService()
        )
        self.repository = (
            repository
            if repository is not None
            else PortfolioSnapshotRepository()
        )

    async def create_snapshot(
        self,
        wallet_id: UUID,
        market_prices: dict[UUID, Decimal],
        session: AsyncSession,
    ) -> list[PortfolioSnapshot]:
        """Calculate and persist one snapshot per portfolio currency."""

        analytics: PortfolioAnalytics = (
            await self.analytics_service.get_analytics(
                wallet_id,
                market_prices,
                session,
            )
        )

        if not analytics.currencies:
            return []

        snapshot_at = datetime.now(timezone.utc)

        snapshots = [
            PortfolioSnapshot(
                wallet_id=wallet_id,
                currency=currency.currency,
                snapshot_at=snapshot_at,
                total_invested=currency.total_invested,
                market_value=currency.market_value,
                realized_pnl=currency.realized_pnl,
                unrealized_pnl=currency.unrealized_pnl,
                total_pnl=currency.total_pnl,
            )
            for currency in analytics.currencies
        ]

        return await self.repository.create_many(
            snapshots,
            session,
        )
