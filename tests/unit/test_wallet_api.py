from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_current_user
from src.core.database import get_db
from src.main import app
from src.models import User, Wallet


@pytest.mark.asyncio
async def test_authenticated_user_can_retrieve_wallet():
    user_id = uuid4()
    wallet_id = uuid4()

    user = User(
        id=user_id,
        email="wallet@example.com",
        password_hash="argon2-hash",
    )

    wallet = Wallet(
        id=wallet_id,
        user_id=user_id,
        balance=Decimal("1500.50000000"),
        currency="USD",
    )

    mock_db = type("MockDB", (), {})()

    async def scalar(statement):
        params = statement.compile().params
        assert user_id in params.values()
        return wallet

    mock_db.scalar = AsyncMock(side_effect=scalar)

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/wallet",
                headers={"Authorization": "Bearer valid-test-token"},
            )

        assert response.status_code == 200
        assert response.json()["id"] == str(wallet_id)
        assert response.json()["balance"] == "1500.50000000"
        assert response.json()["currency"] == "USD"
        mock_db.scalar.assert_awaited_once()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_wallet_endpoint_returns_404_when_wallet_missing():
    user = User(
        id=uuid4(),
        email="missing-wallet@example.com",
        password_hash="argon2-hash",
    )

    mock_db = type("MockDB", (), {})()
    mock_db.scalar = AsyncMock(return_value=None)

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/wallet",
                headers={"Authorization": "Bearer valid-test-token"},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Wallet not found."

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_wallet_endpoint_rejects_missing_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/wallet")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wallet_endpoint_rejects_invalid_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/wallet",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wallet_query_is_scoped_to_authenticated_user():
    authenticated_user_id = uuid4()
    another_user_id = uuid4()

    user = User(
        id=authenticated_user_id,
        email="owner@example.com",
        password_hash="argon2-hash",
    )

    wallet = Wallet(
        id=uuid4(),
        user_id=authenticated_user_id,
        balance=Decimal("250.00"),
        currency="USD",
    )

    mock_db = type("MockDB", (), {})()

    async def scalar(statement):
        params = statement.compile().params

        assert authenticated_user_id in params.values()
        assert another_user_id not in params.values()

        return wallet

    mock_db.scalar = AsyncMock(side_effect=scalar)

    async def override_get_db():
        yield mock_db

    async def override_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/wallet",
                headers={"Authorization": "Bearer valid-test-token"},
            )

        assert response.status_code == 200
        assert response.json()["id"] == str(wallet.id)
        mock_db.scalar.assert_awaited_once()

    finally:
        app.dependency_overrides.clear()
