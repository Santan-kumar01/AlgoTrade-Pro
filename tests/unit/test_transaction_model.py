import uuid
from decimal import Decimal

from sqlalchemy import Numeric

from src.models import Transaction


def test_transaction_uses_uuid_primary_key():
    column = Transaction.__table__.c.id

    assert column.primary_key is True
    assert column.default.arg.__name__ == uuid.uuid4.__name__


def test_transaction_wallet_foreign_key_is_required():
    column = Transaction.__table__.c.wallet_id

    assert column.nullable is False
    foreign_key = next(iter(column.foreign_keys))
    assert foreign_key.target_fullname == "wallets.id"
    assert foreign_key.ondelete == "RESTRICT"


def test_transaction_asset_foreign_key_is_required():
    column = Transaction.__table__.c.asset_id

    assert column.nullable is False
    foreign_key = next(iter(column.foreign_keys))
    assert foreign_key.target_fullname == "assets.id"
    assert foreign_key.ondelete == "RESTRICT"


def test_transaction_type_is_required():
    column = Transaction.__table__.c.transaction_type

    assert column.nullable is False
    assert column.type.length == 4


def test_transaction_quantity_uses_decimal_precision():
    column = Transaction.__table__.c.quantity

    assert isinstance(column.type, Numeric)
    assert column.type.precision == 24
    assert column.type.scale == 8
    assert column.nullable is False


def test_transaction_price_uses_decimal_precision():
    column = Transaction.__table__.c.price

    assert isinstance(column.type, Numeric)
    assert column.type.precision == 24
    assert column.type.scale == 8


def test_transaction_total_amount_uses_decimal_precision():
    column = Transaction.__table__.c.total_amount

    assert isinstance(column.type, Numeric)
    assert column.type.precision == 28
    assert column.type.scale == 8


def test_transaction_has_positive_value_constraints():
    constraint_names = {
        constraint.name
        for constraint in Transaction.__table__.constraints
    }

    assert "ck_transactions_quantity_positive" in constraint_names
    assert "ck_transactions_price_positive" in constraint_names
    assert "ck_transactions_total_amount_positive" in constraint_names


def test_transaction_type_has_buy_sell_constraint():
    constraints = [
        constraint
        for constraint in Transaction.__table__.constraints
        if constraint.name == "ck_transactions_valid_transaction_type"
    ]

    assert len(constraints) == 1


def test_transaction_has_creation_timestamp_only():
    columns = Transaction.__table__.c

    assert "created_at" in columns
    assert "updated_at" not in columns
    assert columns.created_at.nullable is False
    assert columns.created_at.server_default is not None
def test_transaction_total_amount_matches_quantity_times_price():
    constraints = {
        constraint.name
        for constraint in Transaction.__table__.constraints
    }

    assert (
        "ck_transactions_total_amount_matches_quantity_price"
        in constraints
    )

