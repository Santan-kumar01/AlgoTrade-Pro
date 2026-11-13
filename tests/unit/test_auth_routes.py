from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.core.database import get_db


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
