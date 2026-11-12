import uuid
from decimal import Decimal

from sqlalchemy import Numeric

from src.models import Wallet


def test_wallet_uses_uuid_primary_key():
    column = Wallet.__table__.c.id

    assert column.primary_key is True
    assert column.default.arg.__name__ == uuid.uuid4.__name__


def test_wallet_user_id_is_unique_and_required():
    column = Wallet.__table__.c.user_id

    assert column.unique is True
    assert column.nullable is False
    assert any(fk.target_fullname == "users.id" for fk in column.foreign_keys)


def test_wallet_balance_uses_decimal_precision():
    column = Wallet.__table__.c.balance

    assert isinstance(column.type, Numeric)
    assert column.type.precision == 20
    assert column.type.scale == 8
    assert column.nullable is False
    assert column.default.arg == Decimal("0")


def test_wallet_balance_has_non_negative_constraint():
    constraints = [
        constraint
        for constraint in Wallet.__table__.constraints
        if constraint.name == "ck_wallets_balance_non_negative"
    ]

    assert len(constraints) == 1


def test_wallet_currency_defaults_to_usd():
    column = Wallet.__table__.c.currency

    assert column.default.arg == "USD"
    assert column.server_default is not None


def test_wallet_has_timestamp_columns():
    assert "created_at" in Wallet.__table__.c
    assert "updated_at" in Wallet.__table__.c

def test_user_wallet_relationship_is_one_to_one():
    from src.models import User

    assert User.wallet.property.uselist is False
    assert User.wallet.property.back_populates == "user"
    assert Wallet.user.property.back_populates == "wallet"


def test_wallet_user_foreign_key_restricts_deletion():
    column = Wallet.__table__.c.user_id
    foreign_key = next(iter(column.foreign_keys))

    assert foreign_key.ondelete == "RESTRICT"
