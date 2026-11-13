from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.core.database import get_db
from src.api.deps import get_current_user
from src.models import User


@pytest.mark.asyncio
async def test_register_endpoint_returns_created_response():
    user_id = uuid4()

    mock_db = MagicMock()
    mock_db.scalar = AsyncMock(return_value=None)
    mock_db.commit = AsyncMock()

    async def refresh_user(user):
        user.id = user_id

    mock_db.refresh = AsyncMock(side_effect=refresh_user)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("src.api.auth.hash_password", return_value="argon2-hash"):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": "http-test@example.com",
                        "password": "StrongPass@2026",
                    },
                )

        assert response.status_code == 201
        assert response.json()["email"] == "http-test@example.com"
        assert response.json()["id"] == str(user_id)
        assert "password_hash" not in response.json()

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_endpoint_rejects_invalid_email():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "StrongPass@2026",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_endpoint_rejects_short_password():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "http-test@example.com",
                "password": "short",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_endpoint_returns_access_token():
    user = User(
        id=uuid4(),
        email="login@example.com",
        password_hash="argon2-hash",
    )

    mock_db = MagicMock()
    mock_db.scalar = AsyncMock(return_value=user)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("src.api.auth.verify_password", return_value=True), patch(
            "src.api.auth.create_access_token",
            return_value="test-access-token",
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "login@example.com",
                        "password": "StrongPass@2026",
                    },
                )

        assert response.status_code == 200
        assert response.json()["access_token"] == "test-access-token"
        assert response.json()["token_type"] == "bearer"

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_me_endpoint_returns_authenticated_user():
    user = User(
        id=uuid4(),
        email="profile@example.com",
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
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer valid-test-token"},
            )

        assert response.status_code == 200
        assert response.json()["id"] == str(user.id)
        assert response.json()["email"] == "profile@example.com"
        assert "password_hash" not in response.json()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_me_endpoint_rejects_missing_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint_rejects_invalid_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
