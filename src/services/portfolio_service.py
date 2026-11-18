from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Transaction
from src.repositories.trading_repository import TradingRepository


ZERO = Decimal("0")
MAX_DECIMAL_PLACES = 8
MAX_QUANTITY_PRICE_INTEGER_DIGITS = 16
MAX_TOTAL_INTEGER_DIGITS = 20


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    asset_id: UUID
    symbol: str
    name: str
    asset_type: str
    currency: str
    quantity: Decimal
    average_cost: Decimal
    total_invested: Decimal
    realized_pnl: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    wallet_id: UUID
    positions: tuple[PortfolioPosition, ...]
    realized_pnl_by_currency: dict[str, Decimal]


@dataclass(slots=True)
class _PositionState:
    quantity: Decimal = ZERO
    total_cost: Decimal = ZERO
    realized_pnl: Decimal = ZERO


class PortfolioService:
    """Build wallet positions from its immutable transaction ledger."""

    def __init__(
        self,
        repository: TradingRepository | None = None,
    ) -> None:
        self.repository = (
            repository if repository is not None else TradingRepository()
        )

    @staticmethod
    def _validate_transaction(transaction: Transaction) -> None:
        """Validate financial values against database precision limits."""

        values = {
            "quantity": (
                transaction.quantity,
                MAX_QUANTITY_PRICE_INTEGER_DIGITS,
            ),
            "price": (
                transaction.price,
                MAX_QUANTITY_PRICE_INTEGER_DIGITS,
            ),
            "total_amount": (
                transaction.total_amount,
                MAX_TOTAL_INTEGER_DIGITS,
            ),
        }

        for field_name, (value, max_integer_digits) in values.items():
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(
                    f"Transaction {field_name} must be a finite Decimal."
                )

            if value <= ZERO:
                raise ValueError(
                    f"Transaction {field_name} must be positive."
                )

            if value.is_zero():
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

            if decimal_places > MAX_DECIMAL_PLACES:
                raise ValueError(
                    f"Transaction {field_name} exceeds "
                    f"{MAX_DECIMAL_PLACES} decimal places."
                )

            integer_digits = max(0, value.adjusted() + 1)
            if integer_digits > max_integer_digits:
                raise ValueError(
                    f"Transaction {field_name} exceeds "
                    f"the maximum of {max_integer_digits} integer digits."
                )

        with localcontext() as context:
            context.prec = 60
            expected_total = transaction.quantity * transaction.price

        if transaction.total_amount != expected_total:
            raise ValueError(
                "Transaction total_amount must equal quantity multiplied by price."
            )

    async def get_portfolio(
        self,
        wallet_id: UUID,
        session: AsyncSession,
    ) -> PortfolioSummary:
        """Calculate open positions and realized P&L by asset currency."""

        transactions = await self.repository.get_transactions_for_wallet(
            wallet_id,
            session,
        )

        asset_ids = {transaction.asset_id for transaction in transactions}
        assets = await self.repository.get_assets_by_ids(
            asset_ids,
            session,
        )
        assets_by_id = {asset.id: asset for asset in assets}

        missing_asset_ids = asset_ids - assets_by_id.keys()
        if missing_asset_ids:
            raise ValueError(
                f"Asset metadata not found for asset IDs: {missing_asset_ids}."
            )

        states: dict[UUID, _PositionState] = defaultdict(_PositionState)
        realized_pnl_by_currency: dict[str, Decimal] = defaultdict(lambda: ZERO)

        for transaction in transactions:
            self._validate_transaction(transaction)

            state = states[transaction.asset_id]
            asset = assets_by_id[transaction.asset_id]

            realized_pnl_by_currency.setdefault(asset.currency, ZERO)

            if transaction.transaction_type == "BUY":
                with localcontext() as context:
                    context.prec = 60
                    state.quantity += transaction.quantity
                    state.total_cost += transaction.total_amount

            elif transaction.transaction_type == "SELL":
                if state.quantity <= ZERO or transaction.quantity > state.quantity:
                    raise ValueError(
                        "Sell transaction exceeds available historical holdings."
                    )

                with localcontext() as context:
                    context.prec = 60
                    average_cost = state.total_cost / state.quantity
                    cost_basis = average_cost * transaction.quantity
                    realized_pnl = transaction.total_amount - cost_basis

                    state.realized_pnl += realized_pnl
                    realized_pnl_by_currency[asset.currency] += realized_pnl
                    state.quantity -= transaction.quantity
                    state.total_cost -= cost_basis

                    if state.quantity == ZERO:
                        state.total_cost = ZERO

            else:
                raise ValueError(
                    f"Unsupported transaction type: {transaction.transaction_type}"
                )

        positions = []

        for asset_id, state in states.items():
            if state.quantity == ZERO:
                continue

            asset = assets_by_id[asset_id]

            with localcontext() as context:
                context.prec = 60
                average_cost = state.total_cost / state.quantity

            positions.append(
                PortfolioPosition(
                    asset_id=asset.id,
                    symbol=asset.symbol,
                    name=asset.name,
                    asset_type=asset.asset_type,
                    currency=asset.currency,
                    quantity=state.quantity,
                    average_cost=average_cost,
                    total_invested=state.total_cost,
                    realized_pnl=state.realized_pnl,
                )
            )

        positions.sort(key=lambda position: position.symbol)

        return PortfolioSummary(
            wallet_id=wallet_id,
            positions=tuple(positions),
            realized_pnl_by_currency=dict(realized_pnl_by_currency),
        )
