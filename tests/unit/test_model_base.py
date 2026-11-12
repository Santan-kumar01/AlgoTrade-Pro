from sqlalchemy import DateTime

from src.models.base import Base, NAMING_CONVENTION, TimestampMixin


def test_declarative_base_uses_naming_convention():
    """Verify consistent database constraint naming."""
    assert Base.metadata.naming_convention == NAMING_CONVENTION


def test_naming_convention_defines_required_constraints():
    """Verify indexes, constraints, foreign keys and primary keys."""
    assert set(NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}


def test_timestamp_mixin_defines_creation_timestamp():
    """Verify creation timestamps use timezone-aware DateTime."""
    column = TimestampMixin.__dict__["created_at"].column

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.nullable is False
    assert column.server_default is not None


def test_timestamp_mixin_defines_update_timestamp():
    """Verify update timestamps have server defaults and update behavior."""
    column = TimestampMixin.__dict__["updated_at"].column

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.nullable is False
    assert column.server_default is not None
    assert column.onupdate is not None
