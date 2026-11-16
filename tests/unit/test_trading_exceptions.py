from uuid import uuid4
from decimal import Decimal

from src.core.exceptions import (
    TradingEngineException,
    WalletNotFoundError,
    AssetNotFoundError,
    AssetInactiveError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    CurrencyMismatchError,
    InvalidTradeAmountError,
)


def test_wallet_not_found_error():
    user_id = uuid4()
    error = WalletNotFoundError(user_id)

    assert isinstance(error, TradingEngineException)
    assert error.error_code == "WALLET_NOT_FOUND"
    assert error.user_id == user_id


def test_asset_not_found_error():
    asset_id = uuid4()
    error = AssetNotFoundError(asset_id)

    assert error.error_code == "ASSET_NOT_FOUND"
    assert error.asset_id == asset_id


def test_asset_inactive_error():
    error = AssetInactiveError("AAPL")

    assert error.error_code == "ASSET_INACTIVE"
    assert error.symbol == "AAPL"


def test_insufficient_funds_error():
    error = InsufficientFundsError(
        available=Decimal("50.00"),
        required=Decimal("100.00"),
    )

    assert error.error_code == "INSUFFICIENT_FUNDS"
    assert error.available == Decimal("50.00")
    assert error.required == Decimal("100.00")


def test_insufficient_holdings_error():
    error = InsufficientHoldingsError(
        available=Decimal("5"),
        requested=Decimal("10"),
    )

    assert error.error_code == "INSUFFICIENT_HOLDINGS"
    assert error.available == Decimal("5")
    assert error.requested == Decimal("10")


def test_currency_mismatch_error():
    error = CurrencyMismatchError("USD", "EUR")

    assert error.error_code == "CURRENCY_MISMATCH"
    assert error.wallet_currency == "USD"
    assert error.asset_currency == "EUR"


def test_invalid_trade_amount_error():
    error = InvalidTradeAmountError("Invalid decimal precision.")

    assert error.error_code == "INVALID_TRADE_AMOUNT"
    assert error.message == "Invalid decimal precision."


def test_base_exception_preserves_message_and_code():
    error = TradingEngineException("Test error", "TEST_ERROR")

    assert str(error) == "Test error"
    assert error.message == "Test error"
    assert error.error_code == "TEST_ERROR"
