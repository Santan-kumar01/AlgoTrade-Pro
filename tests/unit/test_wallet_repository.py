from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from decimal import Decimal

import pytest
from sqlalchemy.sql import Select

from src.models import Wallet
from src.repositories.wallet_repository import WalletRepository


@pytest.mark.asyncio
async def test_get_wallet_for_update_uses_row_lock():
    wallet_id = uuid4()
    wallet = Wallet(
        id=wallet_id,
        user_id=uuid4(),
        balance=Decimal("100.00"),
        currency="USD",
    )

    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = wallet
    session.execute = AsyncMock(return_value=result)

    repository = WalletRepository()

    returned_wallet = await repository.get_wallet_for_update(
        wallet_id,
        session,
    )

    statement = session.execute.await_args.args[0]

    assert isinstance(statement, Select)
    assert returned_wallet is wallet
    assert statement._for_update_arg is not None


@pytest.mark.asyncio
async def test_get_wallet_for_update_returns_none_when_missing():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    repository = WalletRepository()

    returned_wallet = await repository.get_wallet_for_update(
        uuid4(),
        session,
    )

    assert returned_wallet is None


@pytest.mark.asyncio
async def test_get_wallet_by_user_id_returns_wallet():
    user_id = uuid4()
    wallet = Wallet(
        id=uuid4(),
        user_id=user_id,
        balance=Decimal("250.00"),
        currency="USD",
    )

    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = wallet
    session.execute = AsyncMock(return_value=result)

    repository = WalletRepository()

    returned_wallet = await repository.get_wallet_by_user_id(
        user_id,
        session,
    )

    assert returned_wallet is wallet
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_balance_changes_wallet_balance():
    wallet = Wallet(
        id=uuid4(),
        user_id=uuid4(),
        balance=Decimal("100.00"),
        currency="USD",
    )

    repository = WalletRepository()

    returned_wallet = await repository.update_balance(
        wallet,
        Decimal("75.00"),
    )

    assert returned_wallet is wallet
    assert wallet.balance == Decimal("75.00")
