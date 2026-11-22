from decimal import Decimal, localcontext
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    AssetInactiveError,
    AssetNotFoundError,
    CurrencyMismatchError,
    InsufficientFundsError,
    InsufficientHoldingsError,
    InvalidTradeAmountError,
    WalletNotFoundError,
)
from src.models import Asset, Transaction, Wallet
from src.repositories.trading_repository import TradingRepository
from src.repositories.wallet_repository import WalletRepository


class TradingService:
    """Execute atomic simulated BUY and SELL operations."""

    WALLET_MAX_INTEGER_DIGITS = 12
    TRANSACTION_MAX_INTEGER_DIGITS = 20
    MAX_DECIMAL_PLACES = 8

    def __init__(
        self,
        wallet_repo: WalletRepository | None = None,
        trading_repo: TradingRepository | None = None,
    ) -> None:
        self.wallet_repo = (
            wallet_repo if wallet_repo is not None else WalletRepository()
        )
        self.trading_repo = (
            trading_repo if trading_repo is not None else TradingRepository()
        )

    @classmethod
    def _validate_amount(
        cls,
        value: Decimal,
        max_integer_digits: int,
        field_name: str,
    ) -> None:
        """Reject non-finite, over-precision and oversized Decimal values."""

        if not isinstance(value, Decimal) or not value.is_finite():
            raise InvalidTradeAmountError(
                f"{field_name} must be a finite Decimal value."
            )

        if value.is_zero():
            integer_digits = 0
            decimal_places = 0
        else:
            _, digits, exponent = value.as_tuple()

            trailing_zeros = 0
            for digit in reversed(digits):
                if digit != 0:
                    break
                trailing_zeros += 1

            effective_exponent = exponent + trailing_zeros
            decimal_places = max(-effective_exponent, 0)
            integer_digits = max(value.adjusted() + 1, 0)

        if decimal_places > cls.MAX_DECIMAL_PLACES:
            raise InvalidTradeAmountError(
                f"{field_name} cannot exceed "
                f"{cls.MAX_DECIMAL_PLACES} decimal places."
            )

        if integer_digits > max_integer_digits:
            raise InvalidTradeAmountError(
                f"{field_name} exceeds the supported integer digit limit."
            )

    @classmethod
    def _calculate_total(
        cls,
        quantity: Decimal,
        price: Decimal,
    ) -> Decimal:
        """Calculate a positive transaction total without silent rounding."""

        with localcontext() as context:
            context.prec = 60
            total = quantity * price

        cls._validate_amount(
            total,
            cls.TRANSACTION_MAX_INTEGER_DIGITS,
            "Transaction total",
        )

        if total <= 0:
            raise InvalidTradeAmountError(
                "Transaction total must be greater than zero."
            )

        return total

    async def _get_locked_wallet(
        self,
        user_id: UUID,
        session: AsyncSession,
    ):
        """Acquire the wallet row lock before reading trading state."""

        wallet = await self.wallet_repo.get_wallet_for_user_update(
            user_id,
            session,
        )

        if wallet is None:
            raise WalletNotFoundError(user_id)

        return wallet

    async def _get_tradable_asset(
        self,
        asset_id: UUID,
        wallet,
        session: AsyncSession,
    ):
        """Validate asset existence, activity and currency compatibility."""

        asset = await self.trading_repo.get_asset_by_id(
            asset_id,
            session,
        )

        if asset is None:
            raise AssetNotFoundError(asset_id)

        if not asset.is_active:
            raise AssetInactiveError(asset.symbol)

        if asset.currency != wallet.currency:
            raise CurrencyMismatchError(
                wallet.currency,
                asset.currency,
            )

        return asset

    async def validate_buy_preconditions(
        self,
        user_id: UUID,
        asset_id: UUID,
        quantity: Decimal,
        price: Decimal,
        session: AsyncSession,
    ) -> tuple[Wallet, Asset, Decimal]:
        """Validate all business preconditions for a simulated BUY order.

        Verifies:
        1. Input amounts: Quantity and price are positive, finite Decimals within precision limits.
        2. Total cost: Calculated via exact Decimal arithmetic (quantity * price).
        3. Wallet validation: Resolves the authenticated user's wallet (raising WalletNotFoundError if missing).
        4. Asset validation: Resolves the target asset, verifying it exists, is active (raising AssetNotFoundError
           or AssetInactiveError), and matches the wallet's currency (raising CurrencyMismatchError).
        5. Balance validation: Verifies wallet.balance >= total_cost (raising InsufficientFundsError if balance < total_cost).

        Returns:
            tuple[Wallet, Asset, Decimal]: The locked wallet, tradable asset, and total cost.
        """
        self._validate_amount(quantity, 16, "Quantity")
        self._validate_amount(price, 16, "Price")

        if quantity <= 0 or price <= 0:
            raise InvalidTradeAmountError(
                "Quantity and price must be greater than zero."
            )

        total_cost = self._calculate_total(quantity, price)

        wallet = await self._get_locked_wallet(user_id, session)
        asset = await self._get_tradable_asset(asset_id, wallet, session)

        self._validate_amount(
            wallet.balance,
            self.WALLET_MAX_INTEGER_DIGITS,
            "Wallet balance",
        )

        if wallet.balance < total_cost:
            raise InsufficientFundsError(
                available=wallet.balance,
                required=total_cost,
            )

        return wallet, asset, total_cost

    async def execute_buy(
        self,
        user_id: UUID,
        asset_id: UUID,
        quantity: Decimal,
        price: Decimal,
        session: AsyncSession,
    ) -> Transaction:
        """Deduct wallet funds and insert a BUY ledger record atomically."""
        async with session.begin():
            wallet, asset, total_cost = await self.validate_buy_preconditions(
                user_id=user_id,
                asset_id=asset_id,
                quantity=quantity,
                price=price,
                session=session,
            )

            with localcontext() as context:
                context.prec = 60
                new_balance = wallet.balance - total_cost

            self._validate_amount(
                new_balance,
                self.WALLET_MAX_INTEGER_DIGITS,
                "Updated wallet balance",
            )

            await self.wallet_repo.update_balance(wallet, new_balance)

            transaction = Transaction(
                wallet_id=wallet.id,
                asset_id=asset.id,
                transaction_type="BUY",
                quantity=quantity,
                price=price,
                total_amount=total_cost,
            )

            await self.trading_repo.create_transaction(
                transaction,
                session,
            )

            await session.flush()

        return transaction

    async def validate_sell_preconditions(
        self,
        user_id: UUID,
        asset_id: UUID,
        quantity: Decimal,
        price: Decimal,
        session: AsyncSession,
    ) -> tuple[Wallet, Asset, Decimal]:
        """Validate all business preconditions for a simulated SELL order.

        Verifies:
        1. Input amounts: Quantity and price are positive, finite Decimals within precision limits.
        2. Total proceeds: Calculated via exact Decimal arithmetic (quantity * price).
        3. Wallet validation: Resolves the authenticated user's wallet (raising WalletNotFoundError if missing).
        4. Asset validation: Resolves the target asset, verifying it exists, is active (raising AssetNotFoundError
           or AssetInactiveError), and matches the wallet's currency (raising CurrencyMismatchError).
        5. Balance validation: Validates the current wallet balance format.
        6. Holdings validation: Verifies user net holdings >= quantity (raising InsufficientHoldingsError if net holdings < quantity).

        Returns:
            tuple[Wallet, Asset, Decimal]: The locked wallet, tradable asset, and total proceeds.
        """
        self._validate_amount(quantity, 16, "Quantity")
        self._validate_amount(price, 16, "Price")

        if quantity <= 0 or price <= 0:
            raise InvalidTradeAmountError(
                "Quantity and price must be greater than zero."
            )

        total_proceeds = self._calculate_total(quantity, price)

        wallet = await self._get_locked_wallet(user_id, session)
        asset = await self._get_tradable_asset(asset_id, wallet, session)

        self._validate_amount(
            wallet.balance,
            self.WALLET_MAX_INTEGER_DIGITS,
            "Wallet balance",
        )

        available_holdings = await self.trading_repo.get_net_holdings(
            wallet.id,
            asset.id,
            session,
        )

        if available_holdings < quantity:
            raise InsufficientHoldingsError(
                available=available_holdings,
                requested=quantity,
            )

        return wallet, asset, total_proceeds

    async def execute_sell(
        self,
        user_id: UUID,
        asset_id: UUID,
        quantity: Decimal,
        price: Decimal,
        session: AsyncSession,
    ) -> Transaction:
        """Credit wallet funds and insert a SELL ledger record atomically."""
        async with session.begin():
            wallet, asset, total_proceeds = (
                await self.validate_sell_preconditions(
                    user_id=user_id,
                    asset_id=asset_id,
                    quantity=quantity,
                    price=price,
                    session=session,
                )
            )

            with localcontext() as context:
                context.prec = 60
                new_balance = wallet.balance + total_proceeds

            self._validate_amount(
                new_balance,
                self.WALLET_MAX_INTEGER_DIGITS,
                "Updated wallet balance",
            )

            await self.wallet_repo.update_balance(wallet, new_balance)

            transaction = Transaction(
                wallet_id=wallet.id,
                asset_id=asset.id,
                transaction_type="SELL",
                quantity=quantity,
                price=price,
                total_amount=total_proceeds,
            )

            await self.trading_repo.create_transaction(
                transaction,
                session,
            )

            await session.flush()

        return transaction
