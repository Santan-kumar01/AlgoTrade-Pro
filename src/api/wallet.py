from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.core.database import get_db
from src.models import User, Wallet
from src.schemas import WalletResponse


router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get(
    "",
    response_model=WalletResponse,
)
async def get_my_wallet(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    """Retrieve the authenticated user's wallet."""

    wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id)
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found.",
        )

    return WalletResponse.model_validate(wallet)
