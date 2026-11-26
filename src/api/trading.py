from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user_id
from src.core.database import get_db
from src.core.exceptions import (
    AssetInactiveError,
    AssetNotFoundError,
    CurrencyMismatchError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    InvalidTradeAmountError,
    TradingEngineException,
    TransactionNotFoundError,
    WalletNotFoundError,
)
from src.schemas import (
    BuyOrderRequest,
    SellOrderRequest,
    TradeHistoryItemResponse,
    TradeHistoryResponse,
    TradeResponse,
    TradeType,
)
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    trading_service: TradingService = Depends(get_trading_service),
) -> TradeResponse:
    """Execute an atomic simulated BUY order for the authenticated user."""

    try:
        transaction = await trading_service.execute_buy(
            user_id=current_user_id,
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    trading_service: TradingService = Depends(get_trading_service),
) -> TradeResponse:
    """Execute an atomic simulated SELL order for the authenticated user."""

    try:
        transaction = await trading_service.execute_sell(
            user_id=current_user_id,
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


@router.get(
    "/history",
    response_model=TradeHistoryResponse,
    summary="Get trade transaction history",
)
@router.get(
    "",
    response_model=TradeHistoryResponse,
    include_in_schema=False,
)
async def get_trade_history(
    asset_id: UUID | None = Query(default=None),
    transaction_type: TradeType | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    trading_service: TradingService = Depends(get_trading_service),
) -> TradeHistoryResponse:
    """Retrieve paginated trade transaction history for the authenticated user."""
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

    try:
        return await trading_service.get_transaction_history(
            user_id=current_user_id,
            session=db,
            asset_id=asset_id,
            transaction_type=transaction_type.value if transaction_type else None,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
        )
    except WalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except (InvalidTradeAmountError, TradingEngineException) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get(
    "/holdings",
    response_model=dict[UUID, Decimal],
    summary="Get user current net holdings across all assets",
)
async def get_holdings(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    trading_service: TradingService = Depends(get_trading_service),
) -> dict[UUID, Decimal]:
    """Retrieve positive net holdings derived from transactions for the authenticated user."""
    try:
        return await trading_service.get_user_holdings(
            user_id=current_user_id,
            session=db,
        )
    except WalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except TradingEngineException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get(
    "/{transaction_id}",
    response_model=TradeHistoryItemResponse,
    summary="Get trade transaction details by ID",
)
async def get_trade_by_id(
    transaction_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    trading_service: TradingService = Depends(get_trading_service),
) -> TradeHistoryItemResponse:
    """Retrieve details of a specific transaction for the authenticated user."""
    try:
        return await trading_service.get_transaction_by_id(
            transaction_id=transaction_id,
            user_id=current_user_id,
            session=db,
        )
    except (TransactionNotFoundError, WalletNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
    except TradingEngineException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
