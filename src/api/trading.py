from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.core.database import get_db
from src.core.exceptions import (
    AssetInactiveError,
    AssetNotFoundError,
    CurrencyMismatchError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    InvalidTradeAmountError,
    TradingEngineException,
    WalletNotFoundError,
)
from src.models import User
from src.schemas import BuyOrderRequest, SellOrderRequest, TradeResponse
from src.services.trading_service import TradingService

router = APIRouter(prefix="/trades", tags=["Trading"])


def get_trading_service() -> TradingService:
    """Dependency provider for TradingService."""
    return TradingService()


@router.post(
    "/buy",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute simulated buy order",
)
async def buy_order(
    order_data: BuyOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    trading_service: TradingService = Depends(get_trading_service),
) -> TradeResponse:
    """Execute an atomic simulated BUY order for the authenticated user."""

    try:
        transaction = await trading_service.execute_buy(
            user_id=current_user.id,
            asset_id=order_data.asset_id,
            quantity=order_data.quantity,
            price=order_data.price,
            session=db,
        )
    except (AssetNotFoundError, WalletNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except (
        AssetInactiveError,
        InsufficientFundsError,
        CurrencyMismatchError,
        InvalidTradeAmountError,
        TradingEngineException,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    return TradeResponse.model_validate(transaction)


@router.post(
    "/sell",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute simulated sell order",
)
async def sell_order(
    order_data: SellOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    trading_service: TradingService = Depends(get_trading_service),
) -> TradeResponse:
    """Execute an atomic simulated SELL order for the authenticated user."""

    try:
        transaction = await trading_service.execute_sell(
            user_id=current_user.id,
            asset_id=order_data.asset_id,
            quantity=order_data.quantity,
            price=order_data.price,
            session=db,
        )
    except (AssetNotFoundError, WalletNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except (
        AssetInactiveError,
        InsufficientHoldingsError,
        CurrencyMismatchError,
        InvalidTradeAmountError,
        TradingEngineException,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    return TradeResponse.model_validate(transaction)
