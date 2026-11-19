from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.core.database import get_db
from src.models.user import User
from src.repositories.wallet_repository import WalletRepository
from src.schemas import PortfolioSummaryResponse
from src.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

wallet_repository = WalletRepository()
portfolio_service = PortfolioService()


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
