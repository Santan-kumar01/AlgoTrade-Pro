from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.portfolio_service import ZERO, PortfolioService


@dataclass(frozen=True, slots=True)
class PositionAnalytics:
    asset_id: UUID
    symbol: str
    currency: str
    quantity: Decimal
    average_cost: Decimal
    total_invested: Decimal
    market_price: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    allocation_percentage: Decimal


@dataclass(frozen=True, slots=True)
class CurrencyAnalytics:
    currency: str
    total_invested: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioAnalytics:
    wallet_id: UUID
    positions: tuple[PositionAnalytics, ...]
    currencies: tuple[CurrencyAnalytics, ...]
    concentration_ratio: Decimal | None = None
    concentration_threshold: Decimal = Decimal("50")
    is_concentrated: bool | None = None
    concentrated_positions: tuple[str, ...] = ()


class MarketPriceValidationError(ValueError):
    """Raised when supplied market prices are invalid."""


class PortfolioAnalyticsService:
    """Calculate portfolio analytics using explicitly supplied market prices."""

    def __init__(
        self,
        portfolio_service: PortfolioService | None = None,
        concentration_threshold: Decimal = Decimal("50"),
    ) -> None:
        if (
            not isinstance(concentration_threshold, Decimal)
            or not concentration_threshold.is_finite()
            or concentration_threshold <= ZERO
            or concentration_threshold > Decimal("100")
        ):
            raise ValueError(
                "Concentration threshold must be a finite Decimal "
                "greater than 0 and at most 100."
            )

        self.portfolio_service = (
            portfolio_service if portfolio_service is not None else PortfolioService()
        )
        self.concentration_threshold = concentration_threshold

    @staticmethod
    def _validate_market_prices(
        market_prices: dict[UUID, Decimal],
        position_ids: set[UUID],
    ) -> None:
        if not isinstance(market_prices, dict):
            raise MarketPriceValidationError(
                "Market prices must be provided as a dictionary."
            )

        missing_ids = position_ids - market_prices.keys()
        if missing_ids:
            raise MarketPriceValidationError(
                f"Market prices missing for asset IDs: {missing_ids}."
            )

        unexpected_ids = market_prices.keys() - position_ids
        if unexpected_ids:
            raise MarketPriceValidationError(
                f"Market prices contain unknown asset IDs: {unexpected_ids}."
            )

        for asset_id, price in market_prices.items():
            if not isinstance(price, Decimal) or not price.is_finite():
                raise MarketPriceValidationError(
                    f"Market price for asset {asset_id} must be a finite Decimal."
                )

            if price <= ZERO:
                raise MarketPriceValidationError(
                    f"Market price for asset {asset_id} must be positive."
                )

    async def get_analytics(
        self,
        wallet_id: UUID,
        market_prices: dict[UUID, Decimal],
        session: AsyncSession,
    ) -> PortfolioAnalytics:
        """Calculate position and currency-wise P&L and allocation."""

        if not isinstance(market_prices, dict):
            raise MarketPriceValidationError(
                "Market prices must be provided as a dictionary."
            )

        portfolio = await self.portfolio_service.get_portfolio(
            wallet_id,
            session,
        )

        positions = portfolio.positions
        position_ids = {position.asset_id for position in positions}

        self._validate_market_prices(market_prices, position_ids)

        currency_totals: dict[str, dict[str, Decimal]] = {}

        currencies = set(portfolio.realized_pnl_by_currency) | {
            position.currency for position in positions
        }

        for currency in currencies:
            currency_totals[currency] = {
                "invested": ZERO,
                "market_value": ZERO,
                "realized": portfolio.realized_pnl_by_currency.get(currency, ZERO),
                "unrealized": ZERO,
            }

        with localcontext() as context:
            context.prec = 60

            position_results = []

            for position in positions:
                market_price = market_prices[position.asset_id]
                market_value = position.quantity * market_price
                unrealized_pnl = market_value - position.total_invested
                total_pnl = position.realized_pnl + unrealized_pnl

                totals = currency_totals[position.currency]
                totals["invested"] += position.total_invested
                totals["market_value"] += market_value
                totals["unrealized"] += unrealized_pnl

                position_results.append(
                    PositionAnalytics(
                        asset_id=position.asset_id,
                        symbol=position.symbol,
                        currency=position.currency,
                        quantity=position.quantity,
                        average_cost=position.average_cost,
                        total_invested=position.total_invested,
                        market_price=market_price,
                        market_value=market_value,
                        realized_pnl=position.realized_pnl,
                        unrealized_pnl=unrealized_pnl,
                        total_pnl=total_pnl,
                        allocation_percentage=ZERO,
                    )
                )

            allocation_totals = {
                currency: totals["market_value"]
                for currency, totals in currency_totals.items()
            }

            position_results = [
                replace(
                    position,
                    allocation_percentage=(
                        position.market_value
                        / allocation_totals[position.currency]
                        * Decimal("100")
                        if allocation_totals[position.currency] > ZERO
                        else ZERO
                    ),
                )
                for position in position_results
            ]

            concentration_ratio = None
            is_concentrated = None
            concentrated_positions = ()

            if not position_results:
                is_concentrated = False
                concentration_ratio = ZERO
            elif len(currency_totals) == 1:
                concentration_ratio = max(
                    position.allocation_percentage for position in position_results
                )
                concentrated_positions = tuple(
                    position.symbol
                    for position in position_results
                    if position.allocation_percentage >= self.concentration_threshold
                )
                is_concentrated = concentration_ratio >= self.concentration_threshold

            currency_results = []

            for currency in sorted(currency_totals):
                totals = currency_totals[currency]
                total_pnl = totals["realized"] + totals["unrealized"]

                currency_results.append(
                    CurrencyAnalytics(
                        currency=currency,
                        total_invested=totals["invested"],
                        market_value=totals["market_value"],
                        realized_pnl=totals["realized"],
                        unrealized_pnl=totals["unrealized"],
                        total_pnl=total_pnl,
                    )
                )

        return PortfolioAnalytics(
            wallet_id=wallet_id,
            positions=tuple(position_results),
            currencies=tuple(currency_results),
            concentration_ratio=concentration_ratio,
            concentration_threshold=self.concentration_threshold,
            is_concentrated=is_concentrated,
            concentrated_positions=concentrated_positions,
        )
