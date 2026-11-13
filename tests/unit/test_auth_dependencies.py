from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.deps import get_current_user
from src.models import User


@pytest.mark.asyncio
async def test_get_current_user_returns_existing_user():
    user_id = uuid4()
    user = User(
        id=user_id,
        email="current@example.com",
        password_hash="argon2-hash",
    )

    db = MagicMock()
    db.scalar = AsyncMock(return_value=user)

    with patch(
        "src.api.deps.decode_access_token",
        return_value=user_id,
    ):
        result = await get_current_user(
            token="valid-token",
            db=db,
        )

    assert result is user
    db.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token():
    db = MagicMock()
    db.scalar = AsyncMock()

    with patch(
        "src.api.deps.decode_access_token",
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="invalid-token",
                db=db,
            )

    assert exc_info.value.status_code == 401
    db.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_user_rejects_user_not_found():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)

    with patch(
        "src.api.deps.decode_access_token",
        return_value=uuid4(),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="valid-token",
                db=db,
            )

    assert exc_info.value.status_code == 401
    db.scalar.assert_awaited_once()
