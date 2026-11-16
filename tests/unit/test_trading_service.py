from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.exceptions import (
    AssetInactiveError,
    AssetNotFoundError,
    CurrencyMismatchError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    InvalidTradeAmountError,
    WalletNotFoundError,
)
from src.models import Asset, Transaction
from src.services.trading_service import TradingService


@pytest.fixture
def trading_setup():
    user_id = uuid4()
    asset_id = uuid4()

    wallet = MagicMock()
    wallet.id = uuid4()
    wallet.user_id = user_id
    wallet.balance = Decimal("1000.00000000")
    wallet.currency = "USD"

    asset = MagicMock(spec=Asset)
    asset.id = asset_id
    asset.symbol = "BTC"
    asset.currency = "USD"
    asset.is_active = True

    wallet_repo = MagicMock()
    wallet_repo.get_wallet_for_user_update = AsyncMock(return_value=wallet)
    wallet_repo.update_balance = AsyncMock()

    trading_repo = MagicMock()
    trading_repo.get_asset_by_id = AsyncMock(return_value=asset)
    trading_repo.get_net_holdings = AsyncMock(
        return_value=Decimal("10.00000000")
    )
    trading_repo.create_transaction = AsyncMock()

    session = MagicMock()
    session.begin.return_value = _TransactionContext()
    session.flush = AsyncMock()

    service = TradingService(
        wallet_repo=wallet_repo,
        trading_repo=trading_repo,
    )

    return {
        "service": service,
        "user_id": user_id,
        "asset_id": asset_id,
        "wallet": wallet,
        "asset": asset,
        "wallet_repo": wallet_repo,
        "trading_repo": trading_repo,
        "session": session,
    }


class _TransactionContext:
    """Mock async transaction context for service unit tests."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


@pytest.mark.asyncio
async def test_execute_buy_deducts_balance_and_creates_transaction(
    trading_setup,
):
    setup = trading_setup

    transaction = await setup["service"].execute_buy(
        setup["user_id"],
        setup["asset_id"],
        Decimal("2.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )

    assert isinstance(transaction, Transaction)
    assert transaction.transaction_type == "BUY"
    assert transaction.quantity == Decimal("2.00000000")
    assert transaction.price == Decimal("100.00000000")
    assert transaction.total_amount == Decimal("200.0000000000000000")

    setup["wallet_repo"].update_balance.assert_awaited_once_with(
        setup["wallet"],
        Decimal("800.0000000000000000"),
    )
    setup["trading_repo"].create_transaction.assert_awaited_once_with(
        transaction,
        setup["session"],
    )
    setup["session"].flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_sell_credits_balance_and_creates_transaction(
    trading_setup,
):
    setup = trading_setup

    transaction = await setup["service"].execute_sell(
        setup["user_id"],
        setup["asset_id"],
        Decimal("2.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )

    assert isinstance(transaction, Transaction)
    assert transaction.transaction_type == "SELL"
    assert transaction.total_amount == Decimal("200.0000000000000000")

    setup["wallet_repo"].update_balance.assert_awaited_once_with(
        setup["wallet"],
        Decimal("1200.0000000000000000"),
    )
    setup["trading_repo"].get_net_holdings.assert_awaited_once_with(
        setup["wallet"].id,
        setup["asset_id"],
        setup["session"],
    )
    setup["session"].flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_buy_rejects_missing_wallet(trading_setup):
    setup = trading_setup
    setup["wallet_repo"].get_wallet_for_user_update.return_value = None

    with pytest.raises(WalletNotFoundError):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1"),
            Decimal("100"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_rejects_missing_asset(trading_setup):
    setup = trading_setup
    setup["trading_repo"].get_asset_by_id.return_value = None

    with pytest.raises(AssetNotFoundError):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1"),
            Decimal("100"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_rejects_inactive_asset(trading_setup):
    setup = trading_setup
    setup["asset"].is_active = False

    with pytest.raises(AssetInactiveError):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1"),
            Decimal("100"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_rejects_currency_mismatch(trading_setup):
    setup = trading_setup
    setup["asset"].currency = "EUR"

    with pytest.raises(CurrencyMismatchError):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1"),
            Decimal("100"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_rejects_insufficient_funds(trading_setup):
    setup = trading_setup
    setup["wallet"].balance = Decimal("50.00000000")

    with pytest.raises(InsufficientFundsError):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1"),
            Decimal("100"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_sell_rejects_insufficient_holdings(trading_setup):
    setup = trading_setup
    setup["trading_repo"].get_net_holdings.return_value = Decimal("0.5")

    with pytest.raises(InsufficientHoldingsError):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1"),
            Decimal("100"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.parametrize(
    "value",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("1.123456789"),
        Decimal("10000000000000000"),
        Decimal("-Infinity"),
    ],
)
def test_validate_amount_rejects_invalid_values(value):
    with pytest.raises(InvalidTradeAmountError):
        TradingService._validate_amount(value, 16, "Test amount")


def test_validate_amount_accepts_trailing_decimal_zeros():
    TradingService._validate_amount(
        Decimal("1.230000000"),
        16,
        "Test amount",
    )


def test_calculate_total_uses_exact_decimal_arithmetic():
    total = TradingService._calculate_total(
        Decimal("2.5"),
        Decimal("100.25"),
    )

    assert total == Decimal("250.625")
