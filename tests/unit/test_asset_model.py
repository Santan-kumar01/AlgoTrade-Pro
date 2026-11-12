import uuid

from sqlalchemy import Boolean, Uuid

from src.models import Asset


def test_asset_model_uses_uuid_primary_key():
    """Verify asset IDs use UUID values."""
    column = Asset.__table__.c.id

    assert isinstance(column.type, Uuid)
    assert column.primary_key is True
    assert column.default.arg.__name__ == uuid.uuid4.__name__


def test_asset_symbol_is_unique_and_required():
    """Verify asset symbols are unique and required."""
    column = Asset.__table__.c.symbol

    assert column.unique is True
    assert column.nullable is False
    assert column.type.length == 20


def test_asset_required_fields():
    """Verify required asset information."""
    table = Asset.__table__

    assert table.c.name.nullable is False
    assert table.c.asset_type.nullable is False
    assert table.c.currency.nullable is False


def test_asset_currency_defaults_to_usd():
    """Verify the default asset currency."""
    column = Asset.__table__.c.currency

    assert column.default.arg == "USD"
    assert column.server_default is not None


def test_asset_is_active_by_default():
    """Verify assets are active by default."""
    column = Asset.__table__.c.is_active

    assert isinstance(column.type, Boolean)
    assert column.default.arg is True
    assert column.server_default is not None


def test_asset_has_timestamp_columns():
    """Verify asset timestamps are present."""
    assert "created_at" in Asset.__table__.c
    assert "updated_at" in Asset.__table__.c
