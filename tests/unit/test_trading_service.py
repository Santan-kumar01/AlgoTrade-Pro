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
    setup["trading_repo"].create_transaction.assert_not_awaited()


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
    setup["trading_repo"].create_transaction.assert_not_awaited()


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
    setup["trading_repo"].create_transaction.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_validate_buy_preconditions_success(trading_setup):
    """Verify validate_buy_preconditions passes with valid active asset, wallet, and balance."""
    setup = trading_setup

    wallet, asset, total_cost = await setup["service"].validate_buy_preconditions(
        setup["user_id"],
        setup["asset_id"],
        Decimal("2.00000000"),
        Decimal("150.00000000"),
        setup["session"],
    )

    assert wallet is setup["wallet"]
    assert asset is setup["asset"]
    assert total_cost == Decimal("300.0000000000000000")
    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_buy_preconditions_exact_balance_boundary(trading_setup):
    """Verify validate_buy_preconditions succeeds when wallet balance exactly matches total cost."""
    setup = trading_setup
    setup["wallet"].balance = Decimal("500.00000000")

    wallet, asset, total_cost = await setup["service"].validate_buy_preconditions(
        setup["user_id"],
        setup["asset_id"],
        Decimal("5.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )

    assert total_cost == Decimal("500.0000000000000000")
    assert wallet.balance == total_cost


@pytest.mark.asyncio
async def test_validate_buy_preconditions_rejects_missing_asset(trading_setup):
    """Verify validate_buy_preconditions raises AssetNotFoundError for missing asset."""
    setup = trading_setup
    setup["trading_repo"].get_asset_by_id.return_value = None

    with pytest.raises(AssetNotFoundError) as exc_info:
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.asset_id == setup["asset_id"]


@pytest.mark.asyncio
async def test_validate_buy_preconditions_rejects_inactive_asset(trading_setup):
    """Verify validate_buy_preconditions raises AssetInactiveError for inactive asset."""
    setup = trading_setup
    setup["asset"].is_active = False

    with pytest.raises(AssetInactiveError) as exc_info:
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.symbol == setup["asset"].symbol


@pytest.mark.asyncio
async def test_validate_buy_preconditions_rejects_missing_wallet(trading_setup):
    """Verify validate_buy_preconditions raises WalletNotFoundError when user wallet is missing."""
    setup = trading_setup
    setup["wallet_repo"].get_wallet_for_user_update.return_value = None

    with pytest.raises(WalletNotFoundError) as exc_info:
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.user_id == setup["user_id"]


@pytest.mark.asyncio
async def test_validate_buy_preconditions_rejects_insufficient_funds(trading_setup):
    """Verify validate_buy_preconditions raises InsufficientFundsError when balance < total_cost."""
    setup = trading_setup
    setup["wallet"].balance = Decimal("99.99999999")

    with pytest.raises(InsufficientFundsError) as exc_info:
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.available == Decimal("99.99999999")
    assert exc_info.value.required == Decimal("100.0000000000000000")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "qty,prc",
    [
        (Decimal("0"), Decimal("100")),
        (Decimal("-1"), Decimal("100")),
        (Decimal("10"), Decimal("0")),
        (Decimal("10"), Decimal("-50")),
    ],
)
async def test_validate_buy_preconditions_rejects_non_positive_amounts(
    trading_setup, qty, prc
):
    """Verify validate_buy_preconditions rejects zero or negative quantity and price."""
    setup = trading_setup

    with pytest.raises(InvalidTradeAmountError):
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            qty,
            prc,
            setup["session"],
        )


@pytest.mark.asyncio
async def test_validate_buy_preconditions_propagates_wallet_repository_error(
    trading_setup,
):
    """Verify repository exceptions during wallet lookup propagate without being swallowed."""
    setup = trading_setup
    setup["wallet_repo"].get_wallet_for_user_update.side_effect = RuntimeError(
        "Database connection error"
    )

    with pytest.raises(RuntimeError, match="Database connection error"):
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )


@pytest.mark.asyncio
async def test_validate_buy_preconditions_propagates_trading_repository_error(
    trading_setup,
):
    """Verify repository exceptions during asset lookup propagate without being swallowed."""
    setup = trading_setup
    setup["trading_repo"].get_asset_by_id.side_effect = RuntimeError(
        "Asset table lock timeout"
    )

    with pytest.raises(RuntimeError, match="Asset table lock timeout"):
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )


def test_calculate_total_high_precision_decimals():
    """Verify _calculate_total accurately computes total for high-precision 8-decimal inputs."""
    total = TradingService._calculate_total(
        Decimal("0.00500000"),
        Decimal("45000.50000000"),
    )
    assert total == Decimal("225.00250000000000")


@pytest.mark.asyncio
async def test_validate_buy_preconditions_rejects_currency_mismatch(trading_setup):
    """Verify validate_buy_preconditions raises CurrencyMismatchError on differing currencies."""
    setup = trading_setup
    setup["asset"].currency = "EUR"

    with pytest.raises(CurrencyMismatchError) as exc_info:
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.wallet_currency == "USD"
    assert exc_info.value.asset_currency == "EUR"
    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_resolves_wallet_strictly_by_authenticated_user_id(
    trading_setup,
):
    """Verify execute_buy queries the wallet repository strictly using authenticated user_id."""
    setup = trading_setup

    transaction = await setup["service"].execute_buy(
        setup["user_id"],
        setup["asset_id"],
        Decimal("1.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )

    setup["wallet_repo"].get_wallet_for_user_update.assert_awaited_once_with(
        setup["user_id"],
        setup["session"],
    )
    assert transaction.wallet_id == setup["wallet"].id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "qty,prc",
    [
        (Decimal("NaN"), Decimal("100")),
        (Decimal("10"), Decimal("Infinity")),
        (Decimal("10"), Decimal("-Infinity")),
        (Decimal("1.123456789"), Decimal("100")),
        (Decimal("10"), Decimal("100.123456789")),
        (Decimal("10000000000000000"), Decimal("100")),
        (Decimal("10"), Decimal("10000000000000000")),
    ],
)
async def test_validate_buy_preconditions_rejects_invalid_monetary_inputs(
    trading_setup, qty, prc
):
    """Verify validate_buy_preconditions rejects non-finite and over-precision Decimal values."""
    setup = trading_setup

    with pytest.raises(InvalidTradeAmountError):
        await setup["service"].validate_buy_preconditions(
            setup["user_id"],
            setup["asset_id"],
            qty,
            prc,
            setup["session"],
        )

    setup["wallet_repo"].get_wallet_for_user_update.assert_not_awaited()
    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_succeeds_with_exact_balance_depletion(trading_setup):
    """Verify execute_buy cleanly executes and depletes balance to zero when funds match exactly."""
    setup = trading_setup
    setup["wallet"].balance = Decimal("250.00000000")

    transaction = await setup["service"].execute_buy(
        setup["user_id"],
        setup["asset_id"],
        Decimal("2.50000000"),
        Decimal("100.00000000"),
        setup["session"],
    )

    assert isinstance(transaction, Transaction)
    assert transaction.transaction_type == "BUY"
    assert transaction.quantity == Decimal("2.50000000")
    assert transaction.price == Decimal("100.00000000")
    assert transaction.total_amount == Decimal("250.0000000000000000")

    setup["wallet_repo"].update_balance.assert_awaited_once_with(
        setup["wallet"],
        Decimal("0.0000000000000000"),
    )
    setup["trading_repo"].create_transaction.assert_awaited_once_with(
        transaction,
        setup["session"],
    )


@pytest.mark.asyncio
async def test_execute_buy_rejects_invalid_monetary_inputs_without_side_effects(
    trading_setup,
):
    """Verify execute_buy raises InvalidTradeAmountError and avoids any database mutation."""
    setup = trading_setup

    with pytest.raises(InvalidTradeAmountError):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("NaN"),
            Decimal("100"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_deducts_exact_balance_with_fractional_price(
    trading_setup,
):
    """Verify execute_buy calculates fractional price and deducts exact Decimal total."""
    setup = trading_setup
    setup["wallet"].balance = Decimal("1500.50000000")

    transaction = await setup["service"].execute_buy(
        setup["user_id"],
        setup["asset_id"],
        Decimal("3.25000000"),
        Decimal("42.12500000"),
        setup["session"],
    )

    assert isinstance(transaction, Transaction)
    assert transaction.transaction_type == "BUY"
    assert transaction.quantity == Decimal("3.25000000")
    assert transaction.price == Decimal("42.12500000")
    assert transaction.total_amount == Decimal("136.90625000000000")

    setup["wallet_repo"].update_balance.assert_awaited_once_with(
        setup["wallet"],
        Decimal("1363.59375000000000"),
    )
    setup["trading_repo"].create_transaction.assert_awaited_once_with(
        transaction,
        setup["session"],
    )
    setup["session"].flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_buy_propagates_wallet_repository_update_error(
    trading_setup,
):
    """Verify repository exceptions during update_balance propagate and halt transaction staging."""
    setup = trading_setup
    setup["wallet_repo"].update_balance.side_effect = RuntimeError(
        "Database error updating wallet balance"
    )

    with pytest.raises(
        RuntimeError, match="Database error updating wallet balance"
    ):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    setup["trading_repo"].create_transaction.assert_not_awaited()
    setup["session"].flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_aborts_flush_when_transaction_creation_fails(
    trading_setup,
):
    """Verify failure in create_transaction propagates and halts session flush."""
    setup = trading_setup
    setup["trading_repo"].create_transaction.side_effect = RuntimeError(
        "Ledger insertion failed"
    )

    with pytest.raises(RuntimeError, match="Ledger insertion failed"):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_awaited_once()
    setup["session"].flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_propagates_session_flush_error(trading_setup):
    """Verify failure during session flush propagates without being swallowed."""
    setup = trading_setup
    setup["session"].flush.side_effect = RuntimeError("Session flush failed")

    with pytest.raises(RuntimeError, match="Session flush failed"):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_awaited_once()
    setup["trading_repo"].create_transaction.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "qty,prc",
    [
        (Decimal("0"), Decimal("100")),
        (Decimal("-1"), Decimal("100")),
        (Decimal("10"), Decimal("0")),
        (Decimal("10"), Decimal("-50")),
    ],
)
async def test_execute_buy_rejects_non_positive_amount_without_wallet_mutation(
    trading_setup, qty, prc
):
    """Verify execute_buy rejects non-positive amounts without mutating wallet or creating transaction."""
    setup = trading_setup

    with pytest.raises(InvalidTradeAmountError):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            qty,
            prc,
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()
