import asyncio
from datetime import datetime, timezone
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
    TransactionNotFoundError,
    WalletNotFoundError,
)
from src.models import Asset, Transaction
from src.repositories.trading_repository import TradingRepository
from src.schemas import TradeType
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


@pytest.mark.asyncio
async def test_execute_buy_creates_single_transaction_with_all_expected_fields(
    trading_setup,
):
    """Verify execute_buy creates exactly one immutable transaction with all required fields."""
    setup = trading_setup

    transaction = await setup["service"].execute_buy(
        setup["user_id"],
        setup["asset_id"],
        Decimal("1.50000000"),
        Decimal("250.00000000"),
        setup["session"],
    )

    assert isinstance(transaction, Transaction)
    assert transaction.wallet_id == setup["wallet"].id
    assert transaction.asset_id == setup["asset"].id
    assert transaction.transaction_type == "BUY"
    assert isinstance(transaction.quantity, Decimal)
    assert transaction.quantity == Decimal("1.50000000")
    assert isinstance(transaction.price, Decimal)
    assert transaction.price == Decimal("250.00000000")
    assert isinstance(transaction.total_amount, Decimal)
    assert transaction.total_amount == Decimal("375.0000000000000000")

    setup["trading_repo"].create_transaction.assert_awaited_once_with(
        transaction,
        setup["session"],
    )
    setup["session"].flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_buy_repeated_calls_create_separate_immutable_transactions(
    trading_setup,
):
    """Verify repeated buy calls create distinct transaction instances without modifying prior ones."""
    setup = trading_setup

    tx1 = await setup["service"].execute_buy(
        setup["user_id"],
        setup["asset_id"],
        Decimal("1.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )

    tx2 = await setup["service"].execute_buy(
        setup["user_id"],
        setup["asset_id"],
        Decimal("2.00000000"),
        Decimal("150.00000000"),
        setup["session"],
    )

    assert tx1 is not tx2
    assert tx1.quantity == Decimal("1.00000000")
    assert tx1.price == Decimal("100.00000000")
    assert tx1.total_amount == Decimal("100.0000000000000000")

    assert tx2.quantity == Decimal("2.00000000")
    assert tx2.price == Decimal("150.00000000")
    assert tx2.total_amount == Decimal("300.0000000000000000")

    assert setup["trading_repo"].create_transaction.await_count == 2
    assert setup["trading_repo"].create_transaction.await_args_list[0].args[0] is tx1
    assert setup["trading_repo"].create_transaction.await_args_list[1].args[0] is tx2


@pytest.mark.asyncio
async def test_execute_buy_transaction_persistence_failure_yields_no_successful_response(
    trading_setup,
):
    """Verify transaction persistence failure prevents returning a transaction response."""
    setup = trading_setup
    setup["trading_repo"].create_transaction.side_effect = RuntimeError(
        "Database persistence error"
    )

    with pytest.raises(RuntimeError, match="Database persistence error"):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    setup["session"].flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_buy_session_flush_failure_yields_no_successful_response(
    trading_setup,
):
    """Verify database flush failure propagates and yields no transaction response."""
    setup = trading_setup
    setup["session"].flush.side_effect = RuntimeError(
        "Database flush constraint error"
    )

    with pytest.raises(RuntimeError, match="Database flush constraint error"):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )


def test_trading_repository_exposes_no_transaction_mutation_methods():
    """Verify the repository API contract does not expose update or delete methods for transactions."""
    repository = TradingRepository()
    assert not hasattr(repository, "update_transaction")
    assert not hasattr(repository, "delete_transaction")


@pytest.mark.asyncio
async def test_execute_buy_failure_triggers_transaction_context_exit_with_exception(
    trading_setup,
):
    """Verify that an execution failure triggers transaction context exit with the exception for rollback."""
    setup = trading_setup
    context_mock = AsyncMock()
    context_mock.__aenter__.return_value = context_mock
    context_mock.__aexit__.return_value = False
    setup["session"].begin.return_value = context_mock
    setup["wallet"].balance = Decimal("10.00000000")

    with pytest.raises(InsufficientFundsError):
        await setup["service"].execute_buy(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    context_mock.__aexit__.assert_awaited_once()
    exc_type = context_mock.__aexit__.await_args.args[0]
    assert exc_type is InsufficientFundsError


@pytest.mark.asyncio
async def test_validate_sell_preconditions_success(trading_setup):
    """Verify validate_sell_preconditions passes with valid active asset, wallet, and sufficient holdings."""
    setup = trading_setup

    wallet, asset, total_proceeds = (
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("2.00000000"),
            Decimal("150.00000000"),
            setup["session"],
        )
    )

    assert wallet is setup["wallet"]
    assert asset is setup["asset"]
    assert total_proceeds == Decimal("300.0000000000000000")
    setup["wallet_repo"].get_wallet_for_user_update.assert_awaited_once_with(
        setup["user_id"],
        setup["session"],
    )
    setup["trading_repo"].get_asset_by_id.assert_awaited_once_with(
        setup["asset_id"],
        setup["session"],
    )
    setup["trading_repo"].get_net_holdings.assert_awaited_once_with(
        setup["wallet"].id,
        setup["asset_id"],
        setup["session"],
    )
    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()
    setup["session"].flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_sell_preconditions_exact_holdings_boundary(trading_setup):
    """Verify validate_sell_preconditions succeeds when available holdings exactly match sell quantity."""
    setup = trading_setup
    setup["trading_repo"].get_net_holdings.return_value = Decimal("5.00000000")

    wallet, asset, total_proceeds = (
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("5.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )
    )

    assert total_proceeds == Decimal("500.0000000000000000")
    assert wallet is setup["wallet"]
    assert asset is setup["asset"]


@pytest.mark.asyncio
async def test_validate_sell_preconditions_rejects_insufficient_holdings(trading_setup):
    """Verify validate_sell_preconditions raises InsufficientHoldingsError when holdings < quantity."""
    setup = trading_setup
    setup["trading_repo"].get_net_holdings.return_value = Decimal("4.99999999")

    with pytest.raises(InsufficientHoldingsError) as exc_info:
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("5.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.available == Decimal("4.99999999")
    assert exc_info.value.requested == Decimal("5.00000000")
    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_sell_preconditions_rejects_zero_holdings(trading_setup):
    """Verify validate_sell_preconditions raises InsufficientHoldingsError when user owns zero holdings."""
    setup = trading_setup
    setup["trading_repo"].get_net_holdings.return_value = Decimal("0.00000000")

    with pytest.raises(InsufficientHoldingsError) as exc_info:
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.available == Decimal("0.00000000")
    assert exc_info.value.requested == Decimal("1.00000000")
    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_sell_preconditions_rejects_missing_asset(trading_setup):
    """Verify validate_sell_preconditions raises AssetNotFoundError for missing asset."""
    setup = trading_setup
    setup["trading_repo"].get_asset_by_id.return_value = None

    with pytest.raises(AssetNotFoundError) as exc_info:
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.asset_id == setup["asset_id"]
    setup["trading_repo"].get_net_holdings.assert_not_awaited()
    setup["wallet_repo"].update_balance.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_sell_preconditions_rejects_inactive_asset(trading_setup):
    """Verify validate_sell_preconditions raises AssetInactiveError for inactive asset."""
    setup = trading_setup
    setup["asset"].is_active = False

    with pytest.raises(AssetInactiveError) as exc_info:
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.symbol == setup["asset"].symbol
    setup["trading_repo"].get_net_holdings.assert_not_awaited()
    setup["wallet_repo"].update_balance.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_sell_preconditions_rejects_missing_wallet(trading_setup):
    """Verify validate_sell_preconditions raises WalletNotFoundError when user wallet is missing."""
    setup = trading_setup
    setup["wallet_repo"].get_wallet_for_user_update.return_value = None

    with pytest.raises(WalletNotFoundError) as exc_info:
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.user_id == setup["user_id"]
    setup["trading_repo"].get_asset_by_id.assert_not_awaited()
    setup["trading_repo"].get_net_holdings.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_sell_preconditions_rejects_currency_mismatch(trading_setup):
    """Verify validate_sell_preconditions raises CurrencyMismatchError on differing currencies."""
    setup = trading_setup
    setup["asset"].currency = "EUR"

    with pytest.raises(CurrencyMismatchError) as exc_info:
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.wallet_currency == "USD"
    assert exc_info.value.asset_currency == "EUR"
    setup["trading_repo"].get_net_holdings.assert_not_awaited()
    setup["wallet_repo"].update_balance.assert_not_awaited()


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
async def test_validate_sell_preconditions_rejects_non_positive_amounts(
    trading_setup, qty, prc
):
    """Verify validate_sell_preconditions rejects zero or negative quantity and price."""
    setup = trading_setup

    with pytest.raises(InvalidTradeAmountError):
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            qty,
            prc,
            setup["session"],
        )

    setup["wallet_repo"].get_wallet_for_user_update.assert_not_awaited()
    setup["trading_repo"].get_asset_by_id.assert_not_awaited()
    setup["trading_repo"].get_net_holdings.assert_not_awaited()


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
async def test_validate_sell_preconditions_rejects_invalid_monetary_inputs(
    trading_setup, qty, prc
):
    """Verify validate_sell_preconditions rejects non-finite and over-precision Decimal values."""
    setup = trading_setup

    with pytest.raises(InvalidTradeAmountError):
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            qty,
            prc,
            setup["session"],
        )

    setup["wallet_repo"].get_wallet_for_user_update.assert_not_awaited()
    setup["trading_repo"].get_asset_by_id.assert_not_awaited()
    setup["trading_repo"].get_net_holdings.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_sell_preconditions_propagates_wallet_repository_error(
    trading_setup,
):
    """Verify repository exceptions during wallet lookup propagate without being swallowed."""
    setup = trading_setup
    setup["wallet_repo"].get_wallet_for_user_update.side_effect = RuntimeError(
        "Database connection error"
    )

    with pytest.raises(RuntimeError, match="Database connection error"):
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )


@pytest.mark.asyncio
async def test_validate_sell_preconditions_propagates_asset_repository_error(
    trading_setup,
):
    """Verify repository exceptions during asset lookup propagate without being swallowed."""
    setup = trading_setup
    setup["trading_repo"].get_asset_by_id.side_effect = RuntimeError(
        "Asset table lock timeout"
    )

    with pytest.raises(RuntimeError, match="Asset table lock timeout"):
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )


@pytest.mark.asyncio
async def test_validate_sell_preconditions_propagates_holdings_repository_error(
    trading_setup,
):
    """Verify repository exceptions during net holdings query propagate without being swallowed."""
    setup = trading_setup
    setup["trading_repo"].get_net_holdings.side_effect = RuntimeError(
        "Ledger aggregation query failed"
    )

    with pytest.raises(RuntimeError, match="Ledger aggregation query failed"):
        await setup["service"].validate_sell_preconditions(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )


@pytest.mark.asyncio
async def test_validate_sell_preconditions_performs_no_side_effects(
    trading_setup,
):
    """Verify validate_sell_preconditions causes no database mutations or wallet state changes."""
    setup = trading_setup
    initial_balance = setup["wallet"].balance

    await setup["service"].validate_sell_preconditions(
        setup["user_id"],
        setup["asset_id"],
        Decimal("2.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )

    assert setup["wallet"].balance == initial_balance
    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()
    setup["session"].flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_sell_preconditions_enforces_user_id_isolation(
    trading_setup,
):
    """Verify validate_sell_preconditions queries wallet and holdings strictly by authenticated user."""
    setup = trading_setup

    await setup["service"].validate_sell_preconditions(
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
    setup["trading_repo"].get_net_holdings.assert_awaited_once_with(
        setup["wallet"].id,
        setup["asset_id"],
        setup["session"],
    )


@pytest.mark.asyncio
async def test_execute_sell_credits_exact_balance_with_fractional_price(
    trading_setup,
):
    """Verify execute_sell calculates fractional price and credits exact Decimal total to wallet balance."""
    setup = trading_setup
    setup["wallet"].balance = Decimal("1500.50000000")

    transaction = await setup["service"].execute_sell(
        setup["user_id"],
        setup["asset_id"],
        Decimal("3.25000000"),
        Decimal("42.12500000"),
        setup["session"],
    )

    assert isinstance(transaction, Transaction)
    assert transaction.transaction_type == "SELL"
    assert transaction.quantity == Decimal("3.25000000")
    assert transaction.price == Decimal("42.12500000")
    assert transaction.total_amount == Decimal("136.90625000000000")

    setup["wallet_repo"].update_balance.assert_awaited_once_with(
        setup["wallet"],
        Decimal("1637.40625000000000"),
    )
    setup["trading_repo"].create_transaction.assert_awaited_once_with(
        transaction,
        setup["session"],
    )
    setup["session"].flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_sell_resolves_wallet_strictly_by_authenticated_user_id(
    trading_setup,
):
    """Verify execute_sell queries the wallet repository strictly using authenticated user_id."""
    setup = trading_setup

    transaction = await setup["service"].execute_sell(
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
    setup["trading_repo"].get_net_holdings.assert_awaited_once_with(
        setup["wallet"].id,
        setup["asset_id"],
        setup["session"],
    )
    assert transaction.wallet_id == setup["wallet"].id


@pytest.mark.asyncio
async def test_execute_sell_creates_single_transaction_with_all_expected_fields(
    trading_setup,
):
    """Verify execute_sell creates exactly one immutable transaction with all required fields."""
    setup = trading_setup

    transaction = await setup["service"].execute_sell(
        setup["user_id"],
        setup["asset_id"],
        Decimal("1.50000000"),
        Decimal("250.00000000"),
        setup["session"],
    )

    assert isinstance(transaction, Transaction)
    assert transaction.wallet_id == setup["wallet"].id
    assert transaction.asset_id == setup["asset"].id
    assert transaction.transaction_type == "SELL"
    assert isinstance(transaction.quantity, Decimal)
    assert transaction.quantity == Decimal("1.50000000")
    assert isinstance(transaction.price, Decimal)
    assert transaction.price == Decimal("250.00000000")
    assert isinstance(transaction.total_amount, Decimal)
    assert transaction.total_amount == Decimal("375.0000000000000000")

    setup["trading_repo"].create_transaction.assert_awaited_once_with(
        transaction,
        setup["session"],
    )
    setup["session"].flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_sell_propagates_wallet_repository_update_error(
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
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    setup["trading_repo"].create_transaction.assert_not_awaited()
    setup["session"].flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_sell_aborts_flush_when_transaction_creation_fails(
    trading_setup,
):
    """Verify failure in create_transaction propagates and halts session flush."""
    setup = trading_setup
    setup["trading_repo"].create_transaction.side_effect = RuntimeError(
        "Ledger insertion failed"
    )

    with pytest.raises(RuntimeError, match="Ledger insertion failed"):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_awaited_once()
    setup["session"].flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_sell_transaction_persistence_failure_yields_no_successful_response(
    trading_setup,
):
    """Verify transaction persistence failure prevents returning a transaction response."""
    setup = trading_setup
    setup["trading_repo"].create_transaction.side_effect = RuntimeError(
        "Database persistence error"
    )

    with pytest.raises(RuntimeError, match="Database persistence error"):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    setup["session"].flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_sell_propagates_session_flush_error(trading_setup):
    """Verify failure during session flush propagates without being swallowed."""
    setup = trading_setup
    setup["session"].flush.side_effect = RuntimeError("Session flush failed")

    with pytest.raises(RuntimeError, match="Session flush failed"):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_awaited_once()
    setup["trading_repo"].create_transaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_sell_session_flush_failure_yields_no_successful_response(
    trading_setup,
):
    """Verify database flush failure propagates and yields no transaction response."""
    setup = trading_setup
    setup["session"].flush.side_effect = RuntimeError(
        "Database flush constraint error"
    )

    with pytest.raises(RuntimeError, match="Database flush constraint error"):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )


@pytest.mark.asyncio
async def test_execute_sell_failure_triggers_transaction_context_exit_with_exception(
    trading_setup,
):
    """Verify that an execution failure triggers transaction context exit with the exception for rollback."""
    setup = trading_setup
    context_mock = AsyncMock()
    context_mock.__aenter__.return_value = context_mock
    context_mock.__aexit__.return_value = False
    setup["session"].begin.return_value = context_mock
    setup["trading_repo"].get_net_holdings.return_value = Decimal("0.50000000")

    with pytest.raises(InsufficientHoldingsError):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    context_mock.__aexit__.assert_awaited_once()
    exc_type = context_mock.__aexit__.await_args.args[0]
    assert exc_type is InsufficientHoldingsError


@pytest.mark.asyncio
async def test_execute_sell_unexpected_error_triggers_transaction_context_exit(
    trading_setup,
):
    """Verify unexpected database errors trigger transaction context exit with exception for rollback."""
    setup = trading_setup
    context_mock = AsyncMock()
    context_mock.__aenter__.return_value = context_mock
    context_mock.__aexit__.return_value = False
    setup["session"].begin.return_value = context_mock
    setup["trading_repo"].create_transaction.side_effect = RuntimeError(
        "Disk write failure"
    )

    with pytest.raises(RuntimeError, match="Disk write failure"):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    context_mock.__aexit__.assert_awaited_once()
    exc_type = context_mock.__aexit__.await_args.args[0]
    assert exc_type is RuntimeError


@pytest.mark.asyncio
async def test_execute_sell_repeated_calls_create_separate_immutable_transactions(
    trading_setup,
):
    """Verify repeated sell calls create distinct transaction instances without modifying prior ones."""
    setup = trading_setup

    tx1 = await setup["service"].execute_sell(
        setup["user_id"],
        setup["asset_id"],
        Decimal("1.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )

    tx2 = await setup["service"].execute_sell(
        setup["user_id"],
        setup["asset_id"],
        Decimal("2.00000000"),
        Decimal("150.00000000"),
        setup["session"],
    )

    assert tx1 is not tx2
    assert tx1.quantity == Decimal("1.00000000")
    assert tx1.price == Decimal("100.00000000")
    assert tx1.total_amount == Decimal("100.0000000000000000")

    assert tx2.quantity == Decimal("2.00000000")
    assert tx2.price == Decimal("150.00000000")
    assert tx2.total_amount == Decimal("300.0000000000000000")

    assert setup["trading_repo"].create_transaction.await_count == 2
    assert setup["trading_repo"].create_transaction.await_args_list[0].args[0] is tx1
    assert setup["trading_repo"].create_transaction.await_args_list[1].args[0] is tx2


@pytest.mark.asyncio
async def test_execute_sell_repeated_calls_with_sequential_holdings_depletion(
    trading_setup,
):
    """Verify repeated sell executions correctly account for updated holdings and reject on depletion."""
    setup = trading_setup
    setup["wallet"].balance = Decimal("1000.00000000")

    # First sell: user sells 4 units out of 10 available
    setup["trading_repo"].get_net_holdings.return_value = Decimal("10.00000000")
    tx1 = await setup["service"].execute_sell(
        setup["user_id"],
        setup["asset_id"],
        Decimal("4.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )
    assert tx1.quantity == Decimal("4.00000000")
    assert tx1.total_amount == Decimal("400.0000000000000000")
    setup["wallet"].balance = Decimal("1400.00000000")

    # Second sell: user sells remaining 6 units
    setup["trading_repo"].get_net_holdings.return_value = Decimal("6.00000000")
    tx2 = await setup["service"].execute_sell(
        setup["user_id"],
        setup["asset_id"],
        Decimal("6.00000000"),
        Decimal("100.00000000"),
        setup["session"],
    )
    assert tx2.quantity == Decimal("6.00000000")
    assert tx2.total_amount == Decimal("600.0000000000000000")
    setup["wallet"].balance = Decimal("2000.00000000")

    # Third sell: user attempts to sell 1 unit when holdings are fully depleted (0 available)
    setup["trading_repo"].get_net_holdings.return_value = Decimal("0.00000000")
    with pytest.raises(InsufficientHoldingsError) as exc_info:
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("1.00000000"),
            Decimal("100.00000000"),
            setup["session"],
        )

    assert exc_info.value.available == Decimal("0.00000000")
    assert exc_info.value.requested == Decimal("1.00000000")
    assert tx1 is not tx2
    assert setup["trading_repo"].create_transaction.await_count == 2


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
async def test_execute_sell_rejects_non_positive_amount_without_wallet_mutation(
    trading_setup, qty, prc
):
    """Verify execute_sell rejects non-positive amounts without mutating wallet or creating transaction."""
    setup = trading_setup

    with pytest.raises(InvalidTradeAmountError):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            qty,
            prc,
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_sell_rejects_invalid_monetary_inputs_without_side_effects(
    trading_setup,
):
    """Verify execute_sell raises InvalidTradeAmountError and avoids any database mutation for invalid values."""
    setup = trading_setup

    with pytest.raises(InvalidTradeAmountError):
        await setup["service"].execute_sell(
            setup["user_id"],
            setup["asset_id"],
            Decimal("NaN"),
            Decimal("100"),
            setup["session"],
        )

    setup["wallet_repo"].update_balance.assert_not_awaited()
    setup["trading_repo"].create_transaction.assert_not_awaited()


# ============================================================================
# Service-Level Coroutine Serialization Unit Tests (Python 3.10+)
# ============================================================================


class MockTransactionalState:
    """Manages state snapshotting and rollback simulation for service-level coroutine tests.

    IMPORTANT ARCHITECTURAL NOTE:
    This class models service-level coroutine serialization and transaction rollback
    at the Python asyncio boundary using in-memory locks and state snapshots. It verifies
    that TradingService correctly coordinates with repository dependencies and propagates
    errors, but it does NOT simulate PostgreSQL row-level locks (SELECT FOR UPDATE) or
    MVCC transaction isolation semantics. Full concurrency and row-lock behavior must be
    verified via database-backed integration tests against PostgreSQL.
    """

    def __init__(
        self,
        initial_balance: Decimal,
        initial_holdings: Decimal = Decimal("0"),
    ) -> None:
        self.balance = initial_balance
        self.holdings = initial_holdings
        self.transactions: list[Transaction] = []
        self.lock = asyncio.Lock()

    async def acquire_lock(self, session) -> None:
        """Acquire the state lock on behalf of the session's active transaction."""
        tx_context = getattr(session, "tx_context", None)
        if tx_context is None:
            raise RuntimeError(
                "Cannot acquire lock without an active transaction context on session."
            )
        await tx_context.acquire_lock()

    def create_session(self, wallet):
        state = self

        class MockTxContext:
            def __init__(self):
                self.has_lock = False
                self.snapshot_balance = None
                self.snapshot_holdings = None
                self.snapshot_tx_count = None

            async def acquire_lock(self):
                if self.has_lock:
                    return
                await state.lock.acquire()
                self.has_lock = True
                # Snapshot state strictly AFTER lock acquisition to prevent stale snapshots
                self.snapshot_balance = state.balance
                self.snapshot_holdings = state.holdings
                self.snapshot_tx_count = len(state.transactions)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, tb):
                try:
                    if exc_type is not None and self.has_lock:
                        # Transaction rollback: restore state to snapshot taken upon lock acquisition
                        state.balance = self.snapshot_balance
                        wallet.balance = self.snapshot_balance
                        state.holdings = self.snapshot_holdings
                        state.transactions = state.transactions[
                            : self.snapshot_tx_count
                        ]
                finally:
                    # Release lock ONLY if this transaction context successfully acquired it
                    if self.has_lock:
                        self.has_lock = False
                        state.lock.release()
                return False

        class MockSession:
            def __init__(self):
                self.tx_context = None
                self.flush = AsyncMock()

            def begin(self):
                self.tx_context = MockTxContext()
                return self.tx_context

        return MockSession()


@pytest.mark.asyncio
async def test_concurrent_buys_prevent_overdraft_at_service_boundary():
    """Verify service-level coroutine serialization prevents balance overdraft.

    Demonstrates that when two coroutines execute execute_buy concurrently and the
    repository boundary serializes access, the first debit reduces available balance,
    causing the second operation to fail with InsufficientFundsError and roll back.
    """
    user_id = uuid4()
    asset_id = uuid4()

    wallet = MagicMock()
    wallet.id = uuid4()
    wallet.user_id = user_id
    wallet.balance = Decimal("1000.00000000")
    wallet.currency = "USD"

    asset = MagicMock(spec=Asset)
    asset.id = asset_id
    asset.currency = "USD"
    asset.is_active = True

    tx_state = MockTransactionalState(initial_balance=Decimal("1000.00000000"))

    async def mock_get_wallet(uid, session):
        await tx_state.acquire_lock(session)
        wallet.balance = tx_state.balance
        return wallet

    async def mock_update_balance(w, new_bal):
        tx_state.balance = new_bal
        w.balance = new_bal
        return w

    async def mock_create_tx(tx, session):
        tx_state.transactions.append(tx)
        return tx

    wallet_repo = MagicMock()
    wallet_repo.get_wallet_for_user_update = AsyncMock(side_effect=mock_get_wallet)
    wallet_repo.update_balance = AsyncMock(side_effect=mock_update_balance)

    trading_repo = MagicMock()
    trading_repo.get_asset_by_id = AsyncMock(return_value=asset)
    trading_repo.create_transaction = AsyncMock(side_effect=mock_create_tx)

    service = TradingService(
        wallet_repo=wallet_repo,
        trading_repo=trading_repo,
    )

    ready_event = asyncio.Event()
    counter_lock = asyncio.Lock()
    ready_count = 0

    async def sync():
        nonlocal ready_count
        async with counter_lock:
            ready_count += 1
            if ready_count == 2:
                ready_event.set()
        await asyncio.wait_for(ready_event.wait(), timeout=2.0)

    async def run_buy():
        await sync()
        return await service.execute_buy(
            user_id=user_id,
            asset_id=asset_id,
            quantity=Decimal("1.00000000"),
            price=Decimal("600.00000000"),
            session=tx_state.create_session(wallet),
        )

    results = await asyncio.wait_for(
        asyncio.gather(run_buy(), run_buy(), return_exceptions=True),
        timeout=5.0,
    )

    successes = [r for r in results if isinstance(r, Transaction)]
    failures = [r for r in results if isinstance(r, InsufficientFundsError)]

    assert len(successes) == 1
    assert len(failures) == 1
    # Exactly $600 deducted from $1000; the second failed BUY leaves balance unchanged
    assert wallet.balance == Decimal("400.00000000")
    assert tx_state.balance == Decimal("400.00000000")
    assert len(tx_state.transactions) == 1


@pytest.mark.asyncio
async def test_concurrent_sells_prevent_negative_holdings_at_service_boundary():
    """Verify service-level coroutine serialization prevents holdings overselling.

    Demonstrates that when two coroutines execute execute_sell concurrently and the
    repository boundary serializes access, the first trade depletes holdings, causing
    the second operation to fail with InsufficientHoldingsError and roll back.
    """
    user_id = uuid4()
    asset_id = uuid4()

    wallet = MagicMock()
    wallet.id = uuid4()
    wallet.user_id = user_id
    wallet.balance = Decimal("1000.00000000")
    wallet.currency = "USD"

    asset = MagicMock(spec=Asset)
    asset.id = asset_id
    asset.currency = "USD"
    asset.is_active = True

    tx_state = MockTransactionalState(
        initial_balance=Decimal("1000.00000000"),
        initial_holdings=Decimal("10.00000000"),
    )

    async def mock_get_wallet(uid, session):
        await tx_state.acquire_lock(session)
        wallet.balance = tx_state.balance
        return wallet

    async def mock_update_balance(w, new_bal):
        tx_state.balance = new_bal
        w.balance = new_bal
        return w

    async def mock_get_holdings(wid, aid, session):
        return tx_state.holdings

    async def mock_create_tx(tx, session):
        if tx.transaction_type == "SELL":
            tx_state.holdings -= tx.quantity
        tx_state.transactions.append(tx)
        return tx

    wallet_repo = MagicMock()
    wallet_repo.get_wallet_for_user_update = AsyncMock(side_effect=mock_get_wallet)
    wallet_repo.update_balance = AsyncMock(side_effect=mock_update_balance)

    trading_repo = MagicMock()
    trading_repo.get_asset_by_id = AsyncMock(return_value=asset)
    trading_repo.get_net_holdings = AsyncMock(side_effect=mock_get_holdings)
    trading_repo.create_transaction = AsyncMock(side_effect=mock_create_tx)

    service = TradingService(
        wallet_repo=wallet_repo,
        trading_repo=trading_repo,
    )

    ready_event = asyncio.Event()
    counter_lock = asyncio.Lock()
    ready_count = 0

    async def sync():
        nonlocal ready_count
        async with counter_lock:
            ready_count += 1
            if ready_count == 2:
                ready_event.set()
        await asyncio.wait_for(ready_event.wait(), timeout=2.0)

    async def run_sell():
        await sync()
        return await service.execute_sell(
            user_id=user_id,
            asset_id=asset_id,
            quantity=Decimal("8.00000000"),
            price=Decimal("100.00000000"),
            session=tx_state.create_session(wallet),
        )

    results = await asyncio.wait_for(
        asyncio.gather(run_sell(), run_sell(), return_exceptions=True),
        timeout=5.0,
    )

    successes = [r for r in results if isinstance(r, Transaction)]
    failures = [r for r in results if isinstance(r, InsufficientHoldingsError)]

    assert len(successes) == 1
    assert len(failures) == 1
    # 8 of 10 holdings sold; remaining must be 2; failed SELL rolled back
    assert tx_state.holdings == Decimal("2.00000000")
    # Initial $1000 + $800 proceeds = $1800
    assert wallet.balance == Decimal("1800.00000000")
    assert tx_state.balance == Decimal("1800.00000000")
    assert len(tx_state.transactions) == 1


@pytest.mark.asyncio
async def test_concurrent_buy_and_sell_preserves_balance_and_ledger_at_service_boundary():
    """Verify concurrent BUY and SELL preserve balance and ledger consistency.

    Demonstrates that regardless of which operation acquires the lock first,
    the shared wallet balance and holdings remain consistent:
    - Path A (BUY then SELL): $1000 - $200 = $800, then $800 + $450 = $1250; holdings: 10 + 2 - 3 = 9.
    - Path B (SELL then BUY): $1000 + $450 = $1450, then $1450 - $200 = $1250; holdings: 10 - 3 + 2 = 9.
    """
    user_id = uuid4()
    asset_id = uuid4()

    wallet = MagicMock()
    wallet.id = uuid4()
    wallet.user_id = user_id
    wallet.balance = Decimal("1000.00000000")
    wallet.currency = "USD"

    asset = MagicMock(spec=Asset)
    asset.id = asset_id
    asset.currency = "USD"
    asset.is_active = True

    tx_state = MockTransactionalState(
        initial_balance=Decimal("1000.00000000"),
        initial_holdings=Decimal("10.00000000"),
    )

    async def mock_get_wallet(uid, session):
        await tx_state.acquire_lock(session)
        wallet.balance = tx_state.balance
        return wallet

    async def mock_update_balance(w, new_bal):
        tx_state.balance = new_bal
        w.balance = new_bal
        return w

    async def mock_get_holdings(wid, aid, session):
        return tx_state.holdings

    async def mock_create_tx(tx, session):
        if tx.transaction_type == "BUY":
            tx_state.holdings += tx.quantity
        elif tx.transaction_type == "SELL":
            tx_state.holdings -= tx.quantity
        tx_state.transactions.append(tx)
        return tx

    wallet_repo = MagicMock()
    wallet_repo.get_wallet_for_user_update = AsyncMock(side_effect=mock_get_wallet)
    wallet_repo.update_balance = AsyncMock(side_effect=mock_update_balance)

    trading_repo = MagicMock()
    trading_repo.get_asset_by_id = AsyncMock(return_value=asset)
    trading_repo.get_net_holdings = AsyncMock(side_effect=mock_get_holdings)
    trading_repo.create_transaction = AsyncMock(side_effect=mock_create_tx)

    service = TradingService(
        wallet_repo=wallet_repo,
        trading_repo=trading_repo,
    )

    ready_event = asyncio.Event()
    counter_lock = asyncio.Lock()
    ready_count = 0

    async def sync():
        nonlocal ready_count
        async with counter_lock:
            ready_count += 1
            if ready_count == 2:
                ready_event.set()
        await asyncio.wait_for(ready_event.wait(), timeout=2.0)

    async def run_buy():
        await sync()
        return await service.execute_buy(
            user_id=user_id,
            asset_id=asset_id,
            quantity=Decimal("2.00000000"),
            price=Decimal("100.00000000"),
            session=tx_state.create_session(wallet),
        )

    async def run_sell():
        await sync()
        return await service.execute_sell(
            user_id=user_id,
            asset_id=asset_id,
            quantity=Decimal("3.00000000"),
            price=Decimal("150.00000000"),
            session=tx_state.create_session(wallet),
        )

    results = await asyncio.wait_for(
        asyncio.gather(run_buy(), run_sell(), return_exceptions=True),
        timeout=5.0,
    )

    assert len(results) == 2
    for r in results:
        assert isinstance(r, Transaction)

    # Initial $1,000 - $200 (BUY: 2 @ 100) + $450 (SELL: 3 @ 150) = $1,250
    assert wallet.balance == Decimal("1250.00000000")
    assert tx_state.balance == Decimal("1250.00000000")
    # Initial 10 + 2 (BUY) - 3 (SELL) = 9
    assert tx_state.holdings == Decimal("9.00000000")
    assert len(tx_state.transactions) == 2
    assert {tx.transaction_type for tx in tx_state.transactions} == {
        "BUY",
        "SELL",
    }


@pytest.mark.asyncio
async def test_mock_transactional_state_rollback_and_lock_release_on_exception():
    """Verify MockTransactionalState rolls back state and releases lock on failure.

    Ensures:
    1. Lock ownership is tracked per transaction (lock released only if acquired).
    2. Exceptions inside an active transaction restore balance, holdings, and transactions.
    3. Cancellation unwinding safely releases the held lock and restores state.
    4. Pre-lock failures do not attempt to release or corrupt state.
    """
    tx_state = MockTransactionalState(
        initial_balance=Decimal("1000.00000000"),
        initial_holdings=Decimal("10.00000000"),
    )
    wallet = MagicMock()
    wallet.balance = Decimal("1000.00000000")

    session = tx_state.create_session(wallet)

    # 1. Normal failure after lock acquisition: state is rolled back and lock is released
    with pytest.raises(RuntimeError, match="Simulated failure inside transaction"):
        async with session.begin():
            await tx_state.acquire_lock(session)
            assert session.tx_context.has_lock is True
            assert tx_state.lock.locked() is True

            # Mutate state within transaction
            tx_state.balance = Decimal("500.00000000")
            wallet.balance = Decimal("500.00000000")
            tx_state.holdings = Decimal("5.00000000")
            tx_state.transactions.append(MagicMock())

            raise RuntimeError("Simulated failure inside transaction")

    # Verify rollback
    assert tx_state.balance == Decimal("1000.00000000")
    assert wallet.balance == Decimal("1000.00000000")
    assert tx_state.holdings == Decimal("10.00000000")
    assert len(tx_state.transactions) == 0
    # Verify lock released
    assert not tx_state.lock.locked()
    assert session.tx_context.has_lock is False

    # 2. Failure before lock acquisition: does not touch or release an unacquired lock
    session2 = tx_state.create_session(wallet)
    with pytest.raises(ValueError, match="Pre-lock validation failure"):
        async with session2.begin():
            assert session2.tx_context.has_lock is False
            raise ValueError("Pre-lock validation failure")

    assert session2.tx_context.has_lock is False
    assert not tx_state.lock.locked()

    # 3. Cancellation after lock acquisition: lock is released and state rolled back
    session3 = tx_state.create_session(wallet)
    with pytest.raises(asyncio.CancelledError):
        async with session3.begin():
            await tx_state.acquire_lock(session3)
            assert session3.tx_context.has_lock is True
            assert tx_state.lock.locked() is True

            tx_state.balance = Decimal("200.00000000")
            wallet.balance = Decimal("200.00000000")
            raise asyncio.CancelledError()

    assert tx_state.balance == Decimal("1000.00000000")
    assert wallet.balance == Decimal("1000.00000000")
    assert not tx_state.lock.locked()
    assert session3.tx_context.has_lock is False

    # 4. Attempting to acquire lock without active transaction context raises RuntimeError
    session4 = tx_state.create_session(wallet)
    with pytest.raises(
        RuntimeError,
        match="Cannot acquire lock without an active transaction context on session",
    ):
        await tx_state.acquire_lock(session4)


# ============================================================================
# Phase 6: Transaction History & Holdings Service Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_transaction_history_success(trading_setup):
    """Verify get_transaction_history returns paginated TradeHistoryResponse with joined asset data."""
    setup = trading_setup
    now = datetime.now(timezone.utc)
    tx = Transaction(
        id=uuid4(),
        wallet_id=setup["wallet"].id,
        asset_id=setup["asset_id"],
        transaction_type="BUY",
        quantity=Decimal("1.50000000"),
        price=Decimal("50000.00000000"),
        total_amount=Decimal("75000.00000000"),
        created_at=now,
    )
    asset = Asset(
        id=setup["asset_id"],
        symbol="BTC",
        name="Bitcoin",
        currency="USD",
        is_active=True,
    )

    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=setup["wallet"])
    setup["trading_repo"].get_transaction_history = AsyncMock(return_value=[(tx, asset)])
    setup["trading_repo"].count_transaction_history = AsyncMock(return_value=1)

    result = await setup["service"].get_transaction_history(
        user_id=setup["user_id"],
        session=setup["session"],
        limit=10,
        offset=0,
    )

    assert result.total == 1
    assert result.limit == 10
    assert result.offset == 0
    assert len(result.items) == 1
    item = result.items[0]
    assert item.id == tx.id
    assert item.wallet_id == setup["wallet"].id
    assert item.asset_id == asset.id
    assert item.symbol == "BTC"
    assert item.asset_name == "Bitcoin"
    assert item.transaction_type == TradeType.BUY
    assert item.quantity == Decimal("1.50000000")
    assert item.price == Decimal("50000.00000000")
    assert item.total_amount == Decimal("75000.00000000")
    assert item.currency == "USD"


@pytest.mark.asyncio
async def test_get_transaction_history_wallet_not_found(trading_setup):
    """Verify get_transaction_history raises WalletNotFoundError when user has no wallet."""
    setup = trading_setup
    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=None)

    with pytest.raises(WalletNotFoundError) as exc_info:
        await setup["service"].get_transaction_history(
            user_id=setup["user_id"],
            session=setup["session"],
        )
    assert exc_info.value.user_id == setup["user_id"]


@pytest.mark.asyncio
async def test_get_transaction_history_invalid_date_range(trading_setup):
    """Verify get_transaction_history raises InvalidTradeAmountError when start_at > end_at."""
    setup = trading_setup
    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=setup["wallet"])

    start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(InvalidTradeAmountError, match="start_at cannot be after end_at"):
        await setup["service"].get_transaction_history(
            user_id=setup["user_id"],
            session=setup["session"],
            start_at=start,
            end_at=end,
        )


@pytest.mark.asyncio
async def test_get_transaction_by_id_success(trading_setup):
    """Verify get_transaction_by_id returns TradeHistoryItemResponse for owned transaction."""
    setup = trading_setup
    now = datetime.now(timezone.utc)
    tx = Transaction(
        id=uuid4(),
        wallet_id=setup["wallet"].id,
        asset_id=setup["asset_id"],
        transaction_type="SELL",
        quantity=Decimal("0.50000000"),
        price=Decimal("60000.00000000"),
        total_amount=Decimal("30000.00000000"),
        created_at=now,
    )
    asset = Asset(
        id=setup["asset_id"],
        symbol="BTC",
        name="Bitcoin",
        currency="USD",
        is_active=True,
    )

    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=setup["wallet"])
    setup["trading_repo"].get_transaction_by_id = AsyncMock(return_value=(tx, asset))

    result = await setup["service"].get_transaction_by_id(
        transaction_id=tx.id,
        user_id=setup["user_id"],
        session=setup["session"],
    )

    assert result.id == tx.id
    assert result.transaction_type == TradeType.SELL
    assert result.quantity == Decimal("0.50000000")
    assert result.price == Decimal("60000.00000000")
    assert result.total_amount == Decimal("30000.00000000")
    assert result.symbol == "BTC"
    assert result.asset_name == "Bitcoin"


@pytest.mark.asyncio
async def test_get_transaction_by_id_not_found(trading_setup):
    """Verify get_transaction_by_id raises TransactionNotFoundError if ID does not exist."""
    setup = trading_setup
    tx_id = uuid4()
    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=setup["wallet"])
    setup["trading_repo"].get_transaction_by_id = AsyncMock(return_value=None)

    with pytest.raises(TransactionNotFoundError) as exc_info:
        await setup["service"].get_transaction_by_id(
            transaction_id=tx_id,
            user_id=setup["user_id"],
            session=setup["session"],
        )
    assert exc_info.value.transaction_id == tx_id


@pytest.mark.asyncio
async def test_get_transaction_by_id_wallet_not_found(trading_setup):
    """Verify get_transaction_by_id raises WalletNotFoundError if wallet does not exist."""
    setup = trading_setup
    tx_id = uuid4()
    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=None)

    with pytest.raises(WalletNotFoundError) as exc_info:
        await setup["service"].get_transaction_by_id(
            transaction_id=tx_id,
            user_id=setup["user_id"],
            session=setup["session"],
        )
    assert exc_info.value.user_id == setup["user_id"]


@pytest.mark.asyncio
async def test_get_user_holdings_success(trading_setup):
    """Verify get_user_holdings returns dictionary of net positive holdings."""
    setup = trading_setup
    expected_holdings = {setup["asset_id"]: Decimal("4.25000000")}

    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=setup["wallet"])
    setup["trading_repo"].get_all_net_holdings = AsyncMock(return_value=expected_holdings)

    result = await setup["service"].get_user_holdings(
        user_id=setup["user_id"],
        session=setup["session"],
    )

    assert result == expected_holdings
    setup["trading_repo"].get_all_net_holdings.assert_awaited_once_with(
        wallet_id=setup["wallet"].id,
        session=setup["session"],
    )


@pytest.mark.asyncio
async def test_get_user_holdings_wallet_not_found(trading_setup):
    """Verify get_user_holdings raises WalletNotFoundError if wallet does not exist."""
    setup = trading_setup
    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=None)

    with pytest.raises(WalletNotFoundError) as exc_info:
        await setup["service"].get_user_holdings(
            user_id=setup["user_id"],
            session=setup["session"],
        )
    assert exc_info.value.user_id == setup["user_id"]


@pytest.mark.asyncio
async def test_trading_service_complete_lifecycle(trading_setup):
    """Verify complete TradingService lifecycle: buy -> sell -> history -> holdings -> get_by_id."""
    setup = trading_setup
    now = datetime.now(timezone.utc)
    user_id = setup["user_id"]
    wallet = setup["wallet"]
    asset = Asset(
        id=setup["asset_id"],
        symbol="BTC",
        name="Bitcoin",
        currency="USD",
        is_active=True,
    )
    wallet.balance = Decimal("10000.00000000")

    # 1. Execute BUY
    buy_tx = await setup["service"].execute_buy(
        user_id=user_id,
        asset_id=asset.id,
        quantity=Decimal("5.00000000"),
        price=Decimal("100.00000000"),
        session=setup["session"],
    )
    assert buy_tx.transaction_type == "BUY"
    assert buy_tx.quantity == Decimal("5.00000000")
    assert buy_tx.total_amount == Decimal("500.00000000")

    # 2. Execute SELL
    setup["trading_repo"].get_net_holdings = AsyncMock(return_value=Decimal("5.00000000"))
    sell_tx = await setup["service"].execute_sell(
        user_id=user_id,
        asset_id=asset.id,
        quantity=Decimal("2.00000000"),
        price=Decimal("120.00000000"),
        session=setup["session"],
    )
    assert sell_tx.transaction_type == "SELL"
    assert sell_tx.quantity == Decimal("2.00000000")
    assert sell_tx.total_amount == Decimal("240.00000000")

    # Simulate database column defaults populated on flush/commit
    buy_tx.id = uuid4()
    buy_tx.created_at = now
    sell_tx.id = uuid4()
    sell_tx.created_at = now

    # 3. Query History
    setup["wallet_repo"].get_wallet_by_user_id = AsyncMock(return_value=wallet)
    setup["trading_repo"].get_transaction_history = AsyncMock(return_value=[(sell_tx, asset), (buy_tx, asset)])
    setup["trading_repo"].count_transaction_history = AsyncMock(return_value=2)

    history = await setup["service"].get_transaction_history(
        user_id=user_id,
        session=setup["session"],
        limit=50,
        offset=0,
    )
    assert history.total == 2
    assert len(history.items) == 2
    assert history.items[0].transaction_type == TradeType.SELL
    assert history.items[1].transaction_type == TradeType.BUY

    # 4. Query Holdings
    setup["trading_repo"].get_all_net_holdings = AsyncMock(return_value={asset.id: Decimal("3.00000000")})
    holdings = await setup["service"].get_user_holdings(
        user_id=user_id,
        session=setup["session"],
    )
    assert holdings == {asset.id: Decimal("3.00000000")}

    # 5. Query Transaction By ID
    setup["trading_repo"].get_transaction_by_id = AsyncMock(return_value=(buy_tx, asset))
    item = await setup["service"].get_transaction_by_id(
        transaction_id=buy_tx.id,
        user_id=user_id,
        session=setup["session"],
    )
    assert item.id == buy_tx.id
    assert item.transaction_type == TradeType.BUY
    assert item.symbol == "BTC"
