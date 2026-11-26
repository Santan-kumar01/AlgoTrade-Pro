from uuid import UUID

from decimal import Decimal


class TradingEngineException(Exception):
    """Base exception for trading engine business rule violations."""

    def __init__(self, message: str, error_code: str):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class WalletNotFoundError(TradingEngineException):
    def __init__(self, user_id: UUID):
        super().__init__(
            message="User trading wallet not found.",
            error_code="WALLET_NOT_FOUND",
        )
        self.user_id = user_id


class AssetNotFoundError(TradingEngineException):
    def __init__(self, asset_id: UUID):
        super().__init__(
            message="The specified tradable asset does not exist.",
            error_code="ASSET_NOT_FOUND",
        )
        self.asset_id = asset_id


class AssetInactiveError(TradingEngineException):
    def __init__(self, symbol: str):
        super().__init__(
            message=f"Asset {symbol} is inactive and cannot be traded.",
            error_code="ASSET_INACTIVE",
        )
        self.symbol = symbol


class InsufficientFundsError(TradingEngineException):
    def __init__(self, available: Decimal, required: Decimal):
        super().__init__(
            message="Insufficient wallet balance to execute this buy order.",
            error_code="INSUFFICIENT_FUNDS",
        )
        self.available = available
        self.required = required


class InsufficientHoldingsError(TradingEngineException):
    def __init__(self, available: Decimal, requested: Decimal):
        super().__init__(
            message="Insufficient asset holdings to execute this sell order.",
            error_code="INSUFFICIENT_HOLDINGS",
        )
        self.available = available
        self.requested = requested


class CurrencyMismatchError(TradingEngineException):
    def __init__(self, wallet_currency: str, asset_currency: str):
        super().__init__(
            message="Wallet and asset currencies must match.",
            error_code="CURRENCY_MISMATCH",
        )
        self.wallet_currency = wallet_currency
        self.asset_currency = asset_currency


class InvalidTradeAmountError(TradingEngineException):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="INVALID_TRADE_AMOUNT",
        )


class TransactionNotFoundError(TradingEngineException):
    def __init__(self, transaction_id: UUID):
        super().__init__(
            message=f"Transaction with ID {transaction_id} not found.",
            error_code="TRANSACTION_NOT_FOUND",
        )
        self.transaction_id = transaction_id
