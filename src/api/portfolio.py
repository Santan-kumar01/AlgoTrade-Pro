from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.core.database import get_db
from src.models.user import User
from src.repositories.wallet_repository import WalletRepository
from src.schemas import (
    PortfolioAnalyticsRequest,
    PortfolioAnalyticsResponse,
    PortfolioSummaryResponse,
)
from src.services.portfolio_analytics_service import (
    MarketPriceValidationError,
    PortfolioAnalyticsService,
)
from src.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

wallet_repository = WalletRepository()
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
