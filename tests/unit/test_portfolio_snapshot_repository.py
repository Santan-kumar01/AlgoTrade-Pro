from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.sql import Select

from src.models import PortfolioSnapshot
from src.repositories.portfolio_snapshot_repository import (
    PortfolioSnapshotRepository,
)


def make_snapshot(
    wallet_id=None,
    currency="USD",
    snapshot_at=None,
):
    return PortfolioSnapshot(
        id=uuid4(),
        wallet_id=wallet_id or uuid4(),
        currency=currency,
        snapshot_at=snapshot_at or datetime.now(timezone.utc),
        total_invested=Decimal("100.00"),
        market_value=Decimal("125.00"),
        realized_pnl=Decimal("10.00"),
        unrealized_pnl=Decimal("15.00"),
        total_pnl=Decimal("25.00"),
    )


@pytest.mark.asyncio
async def test_create_adds_snapshot_and_flushes():
    snapshot = make_snapshot()
    session = MagicMock()
    session.flush = AsyncMock()

    repository = PortfolioSnapshotRepository()

    returned = await repository.create(snapshot, session)

    assert returned is snapshot
    session.add.assert_called_once_with(snapshot)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_many_adds_and_flushes_all_snapshots():
    snapshots = [make_snapshot(), make_snapshot(currency="INR")]
    session = MagicMock()
    session.flush = AsyncMock()

    repository = PortfolioSnapshotRepository()

    returned = await repository.create_many(snapshots, session)

    assert returned == snapshots
    session.add_all.assert_called_once_with(snapshots)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_many_returns_empty_list_without_flushing():
    session = MagicMock()
    session.flush = AsyncMock()

    repository = PortfolioSnapshotRepository()

    returned = await repository.create_many([], session)

    assert returned == []
    session.add_all.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_by_id_returns_snapshot_for_wallet():
    wallet_id = uuid4()
    snapshot = make_snapshot(wallet_id=wallet_id)

    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = snapshot
    session.execute = AsyncMock(return_value=result)

    repository = PortfolioSnapshotRepository()

    returned = await repository.get_by_id(
        snapshot.id,
        wallet_id,
        session,
    )

    statement = session.execute.await_args.args[0]

    assert isinstance(statement, Select)
    assert returned is snapshot
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_snapshot_missing():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    repository = PortfolioSnapshotRepository()

    returned = await repository.get_by_id(
        uuid4(),
        uuid4(),
        session,
    )

    assert returned is None


@pytest.mark.asyncio
async def test_get_by_wallet_returns_snapshots():
    wallet_id = uuid4()
    snapshots = [
        make_snapshot(wallet_id=wallet_id),
        make_snapshot(wallet_id=wallet_id, currency="INR"),
    ]

    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = snapshots
    session.execute = AsyncMock(return_value=result)

    repository = PortfolioSnapshotRepository()

    returned = await repository.get_by_wallet(wallet_id, session)

    statement = session.execute.await_args.args[0]

    assert isinstance(statement, Select)
    assert returned == snapshots
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_wallet_applies_currency_and_date_filters():
    wallet_id = uuid4()
    start_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=30)

    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    repository = PortfolioSnapshotRepository()

    returned = await repository.get_by_wallet(
        wallet_id,
        session,
        currency="inr",
        start_at=start_at,
        end_at=end_at,
    )

    statement = session.execute.await_args.args[0]

    assert isinstance(statement, Select)
    assert returned == []
    assert "INR" in str(statement.compile().params.values())
    assert "snapshot_at" in str(statement)


@pytest.mark.asyncio
async def test_get_by_wallet_applies_pagination():
    wallet_id = uuid4()
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    repository = PortfolioSnapshotRepository()

    await repository.get_by_wallet(
        wallet_id,
        session,
        limit=25,
        offset=10,
    )

    statement = session.execute.await_args.args[0]

    assert statement._limit_clause.value == 25
    assert statement._offset_clause.value == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 501, -1])
async def test_get_by_wallet_rejects_invalid_limit(limit):
    repository = PortfolioSnapshotRepository()

    with pytest.raises(ValueError, match="Limit must be between 1 and 500"):
        await repository.get_by_wallet(
            uuid4(),
            MagicMock(),
            limit=limit,
        )


@pytest.mark.asyncio
async def test_get_by_wallet_rejects_negative_offset():
    repository = PortfolioSnapshotRepository()

    with pytest.raises(ValueError, match="Offset cannot be negative"):
        await repository.get_by_wallet(
            uuid4(),
            MagicMock(),
            offset=-1,
        )


@pytest.mark.asyncio
async def test_get_by_wallet_rejects_invalid_date_range():
    repository = PortfolioSnapshotRepository()
    start_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    end_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="start_at cannot be after end_at"):
        await repository.get_by_wallet(
            uuid4(),
            MagicMock(),
            start_at=start_at,
            end_at=end_at,
        )

