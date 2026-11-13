import uuid

import pytest
from pydantic import ValidationError

from src.schemas.auth import UserRegister, UserResponse


def test_registration_schema_accepts_valid_data():
    user = UserRegister(
        email="test@example.com",
        password="StrongPass@2026",
    )

    assert user.email == "test@example.com"
    assert user.password == "StrongPass@2026"


def test_registration_schema_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserRegister(email="invalid-email", password="StrongPass@2026")


def test_registration_schema_rejects_short_password():
    with pytest.raises(ValidationError):
        UserRegister(email="test@example.com", password="short")


def test_registration_schema_rejects_password_over_128_characters():
    with pytest.raises(ValidationError):
        UserRegister(
            email="test@example.com",
            password="A" * 129,
        )


def test_user_response_accepts_uuid_and_email():
    user_id = uuid.uuid4()

    response = UserResponse(
        id=user_id,
        email="test@example.com",
    )

    assert response.id == user_id
    assert response.email == "test@example.com"
    assert "password" not in response.model_dump()


def test_user_response_supports_orm_objects():
    class FakeUser:
        id = uuid.uuid4()
        email = "test@example.com"
        password_hash = "secret-hash"

    response = UserResponse.model_validate(FakeUser())

    assert isinstance(response.id, uuid.UUID)
    assert response.email == "test@example.com"
    assert "password_hash" not in response.model_dump()
