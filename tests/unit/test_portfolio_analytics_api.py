from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_current_user
from src.core.database import get_db
from src.main import app
from src.models import User, Wallet
from src.services.portfolio_analytics_service import (
    CurrencyAnalytics,
    PortfolioAnalytics,
    PositionAnalytics,
)


@pytest.mark.asyncio
async def test_authenticated_user_can_retrieve_portfolio_analytics(
    monkeypatch,
):
    user_id = uuid4()
    wallet_id = uuid4()
    asset_id = uuid4()

    user = User(
        id=user_id,
        email="analytics@example.com",
        password_hash="argon2-hash",
    )

    wallet = Wallet(
        id=wallet_id,
        user_id=user_id,
        balance=Decimal("1500"),
        currency="USD",
    )

    analytics = PortfolioAnalytics(
        wallet_id=wallet_id,
        positions=(
            PositionAnalytics(
                asset_id=asset_id,
                symbol="AAPL",
                currency="USD",
                quantity=Decimal("10"),
                average_cost=Decimal("150"),
                total_invested=Decimal("1500"),
                market_price=Decimal("175"),
                market_value=Decimal("1750"),
                realized_pnl=Decimal("25"),
                unrealized_pnl=Decimal("250"),
                total_pnl=Decimal("275"),
                allocation_percentage=Decimal("100"),
            ),
        ),
        currencies=(
            CurrencyAnalytics(
                currency="USD",
                total_invested=Decimal("1500"),
                market_value=Decimal("1750"),
                realized_pnl=Decimal("25"),
                unrealized_pnl=Decimal("250"),
                total_pnl=Decimal("275"),
            ),
        ),
        concentration_ratio=Decimal("100"),
        concentration_threshold=Decimal("50"),
        is_concentrated=True,
        concentrated_positions=("AAPL",),
    )

    mock_db = AsyncMock()
    mock_wallet_repository = AsyncMock()
    mock_analytics_service = AsyncMock()

    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet
    mock_analytics_service.get_analytics.return_value = analytics

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_analytics_service",
        mock_analytics_service,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/portfolio/analytics",
                json={
                    "market_prices": [
                        {
                            "asset_id": str(asset_id),
                            "market_price": "175",
                        }
                    ]
                },
            )

        assert response.status_code == 200

        data = response.json()

        assert data["wallet_id"] == str(wallet_id)
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "AAPL"
        assert data["positions"][0]["market_value"] == "1750"
        assert data["positions"][0]["unrealized_pnl"] == "250"
        assert data["positions"][0]["total_pnl"] == "275"
        assert data["positions"][0]["allocation_percentage"] == "100"

        assert data["currencies"][0]["currency"] == "USD"
        assert data["currencies"][0]["total_pnl"] == "275"

        assert data["concentration_ratio"] == "100"
        assert data["concentration_threshold"] == "50"
        assert data["is_concentrated"] is True
        assert data["concentrated_positions"] == ["AAPL"]

        mock_wallet_repository.get_wallet_by_user_id.assert_awaited_once_with(
            user_id,
            mock_db,
        )
        mock_analytics_service.get_analytics.assert_awaited_once_with(
            wallet_id,
            {asset_id: Decimal("175")},
            mock_db,
        )

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_analytics_returns_404_when_wallet_missing(monkeypatch):
    user = User(
        id=uuid4(),
        email="missing-analytics@example.com",
        password_hash="argon2-hash",
    )

    mock_wallet_repository = AsyncMock()
    mock_analytics_service = AsyncMock()
    mock_wallet_repository.get_wallet_by_user_id.return_value = None

    async def override_get_db():
        yield AsyncMock()

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_analytics_service",
        mock_analytics_service,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/portfolio/analytics",
                json={"market_prices": []},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Wallet not found."
        mock_analytics_service.get_analytics.assert_not_awaited()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_analytics_returns_422_for_invalid_market_prices(
    monkeypatch,
):
    user_id = uuid4()
    wallet_id = uuid4()
    user = User(
        id=user_id,
        email="invalid-price@example.com",
        password_hash="argon2-hash",
    )
    wallet = Wallet(
        id=wallet_id,
        user_id=user_id,
        balance=Decimal("1500"),
        currency="USD",
    )

    mock_wallet_repository = AsyncMock()
    mock_analytics_service = AsyncMock()
    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet

    from src.services.portfolio_analytics_service import (
        MarketPriceValidationError,
    )

    mock_analytics_service.get_analytics.side_effect = MarketPriceValidationError(
        "Internal validation detail"
    )

    async def override_get_db():
        yield AsyncMock()

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_analytics_service",
        mock_analytics_service,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/portfolio/analytics",
                json={"market_prices": []},
            )

        assert response.status_code == 422
        assert response.json()["detail"] == "Invalid market price data."
        assert "Internal validation detail" not in response.text

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_analytics_returns_500_without_exposing_internal_error(
    monkeypatch,
):
    user_id = uuid4()
    user = User(
        id=user_id,
        email="service-error@example.com",
        password_hash="argon2-hash",
    )
    wallet = Wallet(
        id=uuid4(),
        user_id=user_id,
        balance=Decimal("1500"),
        currency="USD",
    )

    mock_wallet_repository = AsyncMock()
    mock_analytics_service = AsyncMock()
    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet
    mock_analytics_service.get_analytics.side_effect = ValueError(
        "Sensitive internal calculation details"
    )

    async def override_get_db():
        yield AsyncMock()

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_analytics_service",
        mock_analytics_service,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/portfolio/analytics",
                json={"market_prices": []},
            )

        assert response.status_code == 500
        assert response.json()["detail"] == ("Unable to calculate portfolio analytics.")
        assert "Sensitive internal calculation details" not in response.text

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_analytics_rejects_zero_market_price(monkeypatch):
    user = User(
        id=uuid4(),
        email="zero-price@example.com",
        password_hash="argon2-hash",
    )
    mock_analytics_service = AsyncMock()

    monkeypatch.setattr(
        "src.api.portfolio.portfolio_analytics_service",
        mock_analytics_service,
    )

    async def override_get_db():
        yield AsyncMock()

    async def override_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/portfolio/analytics",
                json={
                    "market_prices": [
                        {
                            "asset_id": str(uuid4()),
                            "market_price": "0",
                        }
                    ]
                },
            )

        assert response.status_code == 422
        mock_analytics_service.get_analytics.assert_not_awaited()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_analytics_rejects_duplicate_asset_ids(monkeypatch):
    user = User(
        id=uuid4(),
        email="duplicate-asset@example.com",
        password_hash="argon2-hash",
    )
    asset_id = uuid4()
    mock_analytics_service = AsyncMock()

    monkeypatch.setattr(
        "src.api.portfolio.portfolio_analytics_service",
        mock_analytics_service,
    )

    async def override_get_db():
        yield AsyncMock()

    async def override_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/portfolio/analytics",
                json={
                    "market_prices": [
                        {
                            "asset_id": str(asset_id),
                            "market_price": "175",
                        },
                        {
                            "asset_id": str(asset_id),
                            "market_price": "180",
                        },
                    ]
                },
            )

        assert response.status_code == 422
        mock_analytics_service.get_analytics.assert_not_awaited()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_analytics_rejects_missing_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/portfolio/analytics",
            json={"market_prices": []},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_analytics_rejects_invalid_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/portfolio/analytics",
            headers={"Authorization": "Bearer invalid-token"},
            json={"market_prices": []},
        )

    assert response.status_code == 401
