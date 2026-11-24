from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_current_user
from src.core.database import get_db
from src.main import app
from src.models import PortfolioSnapshot, User, Wallet


def make_snapshot(wallet_id):
    return PortfolioSnapshot(
        id=uuid4(),
        wallet_id=wallet_id,
        currency="USD",
        snapshot_at=datetime.now(timezone.utc),
        total_invested=Decimal("100.00"),
        market_value=Decimal("125.00"),
        realized_pnl=Decimal("10.00"),
        unrealized_pnl=Decimal("15.00"),
        total_pnl=Decimal("25.00"),
    )


@pytest.mark.asyncio
async def test_authenticated_user_can_retrieve_portfolio_snapshots(monkeypatch):
    user_id = uuid4()
    wallet_id = uuid4()
    user = User(
        id=user_id,
        email="snapshot@example.com",
        password_hash="argon2-hash",
    )
    wallet = Wallet(
        id=wallet_id,
        user_id=user_id,
        balance=Decimal("1000.00"),
        currency="USD",
    )
    snapshots = [make_snapshot(wallet_id)]

    mock_db = AsyncMock()
    mock_wallet_repository = AsyncMock()
    mock_snapshot_repository = AsyncMock()

    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet
    mock_snapshot_repository.get_by_wallet.return_value = snapshots

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_snapshot_repository",
        mock_snapshot_repository,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/portfolio/snapshots",
                params={
                    "currency": "USD",
                    "limit": 25,
                    "offset": 5,
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["wallet_id"] == str(wallet_id)
        assert data[0]["currency"] == "USD"
        assert data[0]["total_invested"] == "100.00"
        assert data[0]["market_value"] == "125.00"

        mock_wallet_repository.get_wallet_by_user_id.assert_awaited_once_with(
            user_id,
            mock_db,
        )
        mock_snapshot_repository.get_by_wallet.assert_awaited_once_with(
            wallet_id,
            mock_db,
            currency="USD",
            start_at=None,
            end_at=None,
            limit=25,
            offset=5,
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_snapshot_endpoint_returns_empty_list(monkeypatch):
    user_id = uuid4()
    user = User(
        id=user_id,
        email="empty-snapshot@example.com",
        password_hash="argon2-hash",
    )
    wallet = Wallet(
        id=uuid4(),
        user_id=user_id,
        balance=Decimal("0"),
        currency="USD",
    )

    mock_db = AsyncMock()
    mock_wallet_repository = AsyncMock()
    mock_snapshot_repository = AsyncMock()

    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet
    mock_snapshot_repository.get_by_wallet.return_value = []

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_snapshot_repository",
        mock_snapshot_repository,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/portfolio/snapshots")

        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_snapshot_endpoint_returns_404_when_wallet_missing(monkeypatch):
    user = User(
        id=uuid4(),
        email="missing-snapshot@example.com",
        password_hash="argon2-hash",
    )

    mock_db = AsyncMock()
    mock_wallet_repository = AsyncMock()
    mock_snapshot_repository = AsyncMock()
    mock_wallet_repository.get_wallet_by_user_id.return_value = None

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_snapshot_repository",
        mock_snapshot_repository,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/portfolio/snapshots")

        assert response.status_code == 404
        assert response.json()["detail"] == "Wallet not found."
        mock_snapshot_repository.get_by_wallet.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_snapshot_endpoint_passes_date_filters(monkeypatch):
    user_id = uuid4()
    wallet_id = uuid4()
    user = User(
        id=user_id,
        email="date-snapshot@example.com",
        password_hash="argon2-hash",
    )
    wallet = Wallet(
        id=wallet_id,
        user_id=user_id,
        balance=Decimal("100.00"),
        currency="USD",
    )
    start_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_at = datetime(2026, 1, 31, tzinfo=timezone.utc)

    mock_db = AsyncMock()
    mock_wallet_repository = AsyncMock()
    mock_snapshot_repository = AsyncMock()
    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet
    mock_snapshot_repository.get_by_wallet.return_value = []

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_snapshot_repository",
        mock_snapshot_repository,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/portfolio/snapshots",
                params={
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat(),
                },
            )

        assert response.status_code == 200
        mock_snapshot_repository.get_by_wallet.assert_awaited_once_with(
            wallet_id,
            mock_db,
            currency=None,
            start_at=start_at,
            end_at=end_at,
            limit=100,
            offset=0,
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_snapshot_endpoint_rejects_reversed_date_range(monkeypatch):
    user_id = uuid4()
    user = User(
        id=user_id,
        email="reversed-date@example.com",
        password_hash="argon2-hash",
    )
    wallet = Wallet(
        id=uuid4(),
        user_id=user_id,
        balance=Decimal("100.00"),
        currency="USD",
    )

    mock_db = AsyncMock()
    mock_wallet_repository = AsyncMock()
    mock_snapshot_repository = AsyncMock()
    mock_wallet_repository.get_wallet_by_user_id.return_value = wallet

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    monkeypatch.setattr(
        "src.api.portfolio.wallet_repository",
        mock_wallet_repository,
    )
    monkeypatch.setattr(
        "src.api.portfolio.portfolio_snapshot_repository",
        mock_snapshot_repository,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/portfolio/snapshots",
                params={
                    "start_at": "2026-01-31T00:00:00+00:00",
                    "end_at": "2026-01-01T00:00:00+00:00",
                },
            )

        assert response.status_code == 422
        assert response.json()["detail"] == "start_at cannot be after end_at."
        mock_snapshot_repository.get_by_wallet.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_snapshot_endpoint_rejects_invalid_pagination(monkeypatch):
    user = User(
        id=uuid4(),
        email="invalid-pagination@example.com",
        password_hash="argon2-hash",
    )

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/portfolio/snapshots",
                params={"limit": 0},
            )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
