from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.api.auth import login_user, register_user
from src.core.security import verify_password
from src.models import User
from src.schemas.auth import UserLogin, UserRegister


@pytest.mark.asyncio
async def test_successful_user_registration():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    def add_user(user):
        user.id = uuid4()

    db.add.side_effect = add_user

    user_data = UserRegister(
        email="test@example.com",
        password="StrongPass@2026",
    )

    response = await register_user(user_data, db)

    saved_user = db.add.call_args.args[0]

    assert isinstance(saved_user, User)
    assert response.email == "test@example.com"
    assert response.id == saved_user.id
    assert verify_password(
        "StrongPass@2026",
        saved_user.password_hash,
    )
    assert saved_user.password_hash != "StrongPass@2026"

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(saved_user)


@pytest.mark.asyncio
async def test_registration_rejects_duplicate_email():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=User())
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    user_data = UserRegister(
        email="existing@example.com",
        password="StrongPass@2026",
    )

    with pytest.raises(HTTPException) as exc_info:
        await register_user(user_data, db)

    assert exc_info.value.status_code == 409
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_registration_rolls_back_integrity_error():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    db.commit = AsyncMock(
        side_effect=IntegrityError(
            "INSERT",
            {},
            Exception("unique constraint violation"),
        )
    )
    db.rollback = AsyncMock()

    user_data = UserRegister(
        email="race@example.com",
        password="StrongPass@2026",
    )

    with pytest.raises(HTTPException) as exc_info:
        await register_user(user_data, db)

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_registration_normalizes_email():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    def add_user(user):
        user.id = uuid4()

    db.add.side_effect = add_user

    user_data = UserRegister(
        email="TEST@example.com",
        password="StrongPass@2026",
    )

    response = await register_user(user_data, db)

    assert response.email == "test@example.com"



@pytest.mark.asyncio
async def test_successful_user_login_returns_access_token():
    user_id = uuid4()
    user = User(
        id=user_id,
        email="test@example.com",
        password_hash="argon2-hash",
    )

    db = MagicMock()
    db.scalar = AsyncMock(return_value=user)

    credentials = UserLogin(
        email="test@example.com",
        password="StrongPass@2026",
    )

    with patch(
        "src.api.auth.verify_password",
        return_value=True,
    ), patch(
        "src.api.auth.create_access_token",
        return_value="test-access-token",
    ) as token_mock:
        response = await login_user(credentials, db)

    assert response.access_token == "test-access-token"
    assert response.token_type == "bearer"
    token_mock.assert_called_once_with(user_id)


@pytest.mark.asyncio
async def test_login_rejects_unknown_email():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)

    credentials = UserLogin(
        email="unknown@example.com",
        password="StrongPass@2026",
    )

    with pytest.raises(HTTPException) as exc_info:
        await login_user(credentials, db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password."


@pytest.mark.asyncio
async def test_login_rejects_incorrect_password():
    user = User(
        id=uuid4(),
        email="test@example.com",
        password_hash="argon2-hash",
    )

    db = MagicMock()
    db.scalar = AsyncMock(return_value=user)

    credentials = UserLogin(
        email="test@example.com",
        password="WrongPassword@2026",
    )

    with patch(
        "src.api.auth.verify_password",
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await login_user(credentials, db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password."
