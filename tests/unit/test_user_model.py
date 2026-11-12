import uuid

from sqlalchemy import Uuid

from src.models import User


def test_user_model_uses_uuid_primary_key():
    """Verify user IDs use UUID values."""
    column = User.__table__.c.id

    assert isinstance(column.type, Uuid)
    assert column.primary_key is True
    assert column.default.arg.__name__ == uuid.uuid4.__name__


def test_user_email_is_unique_and_required():
    """Verify email has a unique constraint and is required."""
    column = User.__table__.c.email

    assert column.unique is True
    assert column.nullable is False
    assert column.type.length == 255


def test_user_password_hash_is_required():
    """Verify password hashes cannot be null."""
    column = User.__table__.c.password_hash

    assert column.nullable is False
    assert column.type.length == 255


def test_user_has_timestamp_columns():
    """Verify creation and update timestamps are present."""
    assert "created_at" in User.__table__.c
    assert "updated_at" in User.__table__.c

