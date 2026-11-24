from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.core.database import get_db
from src.models.user import User
from src.repositories.portfolio_snapshot_repository import PortfolioSnapshotRepository
from src.repositories.wallet_repository import WalletRepository
from src.schemas import (
    PortfolioAnalyticsRequest,
    PortfolioAnalyticsResponse,
    PortfolioSummaryResponse,
    PortfolioSnapshotResponse,
)
from src.services.portfolio_analytics_service import (
    MarketPriceValidationError,
    PortfolioAnalyticsService,
)
from src.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

wallet_repository = WalletRepository()
portfolio_snapshot_repository = PortfolioSnapshotRepository()
portfolio_service = PortfolioService()
portfolio_analytics_service = PortfolioAnalyticsService(
    portfolio_service=portfolio_service,
)


@router.get("", response_model=PortfolioSummaryResponse)
async def get_my_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioSummaryResponse:
    """Return the authenticated user's portfolio summary."""

    wallet = await wallet_repository.get_wallet_by_user_id(
        current_user.id,
        db,
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found.",
        )

    try:
        portfolio = await portfolio_service.get_portfolio(wallet.id, db)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate portfolio.",
        ) from None

    return PortfolioSummaryResponse.model_validate(portfolio)


@router.post(
    "/analytics",
    response_model=PortfolioAnalyticsResponse,
)
async def get_my_portfolio_analytics(
    request: PortfolioAnalyticsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioAnalyticsResponse:
    """Return market valuation and performance analytics for the user's portfolio."""

    wallet = await wallet_repository.get_wallet_by_user_id(
        current_user.id,
        db,
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found.",
        )

    market_prices = {
        item.asset_id: item.market_price
        for item in request.market_prices
    }

    try:
        analytics = await portfolio_analytics_service.get_analytics(
            wallet.id,
            market_prices,
            db,
        )
    except MarketPriceValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid market price data.",
        ) from None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate portfolio analytics.",
        ) from None

    return PortfolioAnalyticsResponse.model_validate(analytics)





@router.get(
    "/snapshots",
    response_model=list[PortfolioSnapshotResponse],
)
async def get_my_portfolio_snapshots(
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PortfolioSnapshotResponse]:
    """Return historical snapshots belonging to the authenticated user."""

    wallet = await wallet_repository.get_wallet_by_user_id(
        current_user.id,
        db,
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found.",
        )

    if start_at is not None and (
        start_at.tzinfo is None or start_at.utcoffset() is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_at must include a timezone.",
        )

    if end_at is not None and (
        end_at.tzinfo is None or end_at.utcoffset() is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_at must include a timezone.",
        )

    if start_at is not None and end_at is not None and start_at > end_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_at cannot be after end_at.",
        )

    snapshots = await portfolio_snapshot_repository.get_by_wallet(
        wallet.id,
        db,
        currency=currency,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        offset=offset,
    )

    return [
        PortfolioSnapshotResponse.model_validate(snapshot)
        for snapshot in snapshots
    ]
