from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_current_user
from src.core.database import get_db
from src.main import app
from src.models import User, Wallet
from src.services.portfolio_service import PortfolioPosition, PortfolioSummary


@pytest.mark.asyncio
async def test_authenticated_user_can_retrieve_portfolio(monkeypatch):
    user_id = uuid4()
    wallet_id = uuid4()
    asset_id = uuid4()

    user = User(
        id=user_id,
        email="portfolio@example.com",
        password_hash="argon2-hash",
    )

    wallet = Wallet(
        id=wallet_id,
        user_id=user_id,
        balance=Decimal("1500.00"),
        currency="USD",
    )

    position = PortfolioPosition(
        asset_id=asset_id,
        symbol="AAPL",
        name="Apple Inc.",
        asset_type="STOCK",
        currency="USD",
        quantity=Decimal("10"),
        average_cost=Decimal("150"),
        total_invested=Decimal("1500"),
        realized_pnl=Decimal("25"),
    )

    summary = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(position,),
        realized_pnl_by_currency={"USD": Decimal("25")},
    )

    mock_db = AsyncMock()
    mock_wallet_repository = AsyncMock()
    mock_portfolio_service = AsyncMock()

    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet
    mock_portfolio_service.get_portfolio.return_value = summary

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_service",
        mock_portfolio_service,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/portfolio",
                headers={"Authorization": "Bearer valid-test-token"},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["wallet_id"] == str(wallet_id)
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "AAPL"
        assert data["positions"][0]["quantity"] == "10"
        assert data["realized_pnl_by_currency"]["USD"] == "25"

        mock_wallet_repository.get_wallet_by_user_id.assert_awaited_once_with(
            user_id,
            mock_db,
        )
        mock_portfolio_service.get_portfolio.assert_awaited_once_with(
            wallet_id,
            mock_db,
        )

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_endpoint_returns_empty_portfolio(monkeypatch):
    user_id = uuid4()
    wallet_id = uuid4()

    user = User(
        id=user_id,
        email="empty-portfolio@example.com",
        password_hash="argon2-hash",
    )

    wallet = Wallet(
        id=wallet_id,
        user_id=user_id,
        balance=Decimal("0"),
        currency="USD",
    )

    summary = PortfolioSummary(
        wallet_id=wallet_id,
        positions=(),
        realized_pnl_by_currency={},
    )

    mock_db = AsyncMock()
    mock_wallet_repository = AsyncMock()
    mock_portfolio_service = AsyncMock()

    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet
    mock_portfolio_service.get_portfolio.return_value = summary

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_service",
        mock_portfolio_service,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/portfolio")

        assert response.status_code == 200
        assert response.json()["positions"] == []
        assert response.json()["realized_pnl_by_currency"] == {}

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_endpoint_returns_404_when_wallet_missing(monkeypatch):
    user = User(
        id=uuid4(),
        email="missing-portfolio@example.com",
        password_hash="argon2-hash",
    )

    mock_wallet_repository = AsyncMock()

    mock_wallet_repository.get_wallet_by_user_id.return_value = None

    async def override_get_db():
        yield AsyncMock()

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/portfolio")

        assert response.status_code == 404
        assert response.json()["detail"] == "Wallet not found."

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_portfolio_endpoint_rejects_missing_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/portfolio")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_endpoint_rejects_invalid_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_endpoint_hides_internal_service_errors(monkeypatch):
    user = User(
        id=uuid4(),
        email="service-error@example.com",
        password_hash="argon2-hash",
    )

    wallet = Wallet(
        id=uuid4(),
        user_id=user.id,
        balance=Decimal("100"),
        currency="USD",
    )

    mock_wallet_repository = AsyncMock()
    mock_portfolio_service = AsyncMock()

    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet
    mock_portfolio_service.get_portfolio.side_effect = ValueError(
        "Sensitive internal ledger validation details."
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
        "src.api.portfolio.portfolio_service",
        mock_portfolio_service,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/portfolio")

        assert response.status_code == 500
        assert response.json()["detail"] == "Unable to calculate portfolio."
        assert "Sensitive internal" not in response.text

    finally:
        app.dependency_overrides.clear()
