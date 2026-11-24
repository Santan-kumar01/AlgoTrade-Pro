import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.core.exceptions import (
    InsufficientFundsError,
    InsufficientHoldingsError,
)
from src.models import Transaction, Wallet
from src.repositories.trading_repository import TradingRepository
from src.services.trading_service import TradingService


@pytest.mark.asyncio
async def test_buy_executes_and_persists_atomically(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify BUY updates the wallet and persists its ledger entry."""
    user, wallet = trading_user
    service = TradingService()

    async with db_session_factory() as session:
        transaction = await service.execute_buy(
            user_id=user.id,
            asset_id=trading_asset.id,
            quantity=Decimal("2.00000000"),
            price=Decimal("100.00000000"),
            session=session,
        )

        transaction_id = transaction.id

    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )
        saved_transaction = await verification_session.get(
            Transaction,
            transaction_id,
        )

        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("9800.00000000")

        assert saved_transaction is not None
        assert saved_transaction.transaction_type == "BUY"
        assert saved_transaction.quantity == Decimal("2.00000000")
        assert saved_transaction.price == Decimal("100.00000000")
        assert saved_transaction.total_amount == Decimal("200.00000000")
        assert saved_transaction.wallet_id == wallet.id
        assert saved_transaction.asset_id == trading_asset.id

@pytest.mark.asyncio
async def test_sell_executes_and_persists_atomically(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify SELL credits the wallet and persists its ledger entry."""
    user, wallet = trading_user
    service = TradingService()

    async with db_session_factory() as session:
        await service.execute_buy(
            user_id=user.id,
            asset_id=trading_asset.id,
            quantity=Decimal("5.00000000"),
            price=Decimal("100.00000000"),
            session=session,
        )

    async with db_session_factory() as session:
        transaction = await service.execute_sell(
            user_id=user.id,
            asset_id=trading_asset.id,
            quantity=Decimal("2.00000000"),
            price=Decimal("120.00000000"),
            session=session,
        )
        transaction_id = transaction.id

    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )
        saved_transaction = await verification_session.get(
            Transaction,
            transaction_id,
        )

        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("9740.00000000")

        assert saved_transaction is not None
        assert saved_transaction.transaction_type == "SELL"
        assert saved_transaction.quantity == Decimal("2.00000000")
        assert saved_transaction.price == Decimal("120.00000000")
        assert saved_transaction.total_amount == Decimal("240.00000000")



@pytest.mark.asyncio
async def test_insufficient_funds_preserves_wallet_and_ledger(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify a rejected BUY leaves the database unchanged."""
    user, wallet = trading_user
    service = TradingService()

    with pytest.raises(InsufficientFundsError) as exc_info:
        async with db_session_factory() as session:
            await service.execute_buy(
                user_id=user.id,
                asset_id=trading_asset.id,
                quantity=Decimal("200.00000000"),
                price=Decimal("100.00000000"),
                session=session,
            )

    assert exc_info.value.error_code == "INSUFFICIENT_FUNDS"

    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )

        result = await verification_session.execute(
            select(Transaction).where(
                Transaction.wallet_id == wallet.id,
                Transaction.asset_id == trading_asset.id,
            )
        )
        transactions = result.scalars().all()

        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("10000.00000000")
        assert transactions == []



@pytest.mark.asyncio
async def test_insufficient_holdings_preserves_wallet_and_ledger(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify a rejected SELL leaves the database unchanged."""
    user, wallet = trading_user
    service = TradingService()

    with pytest.raises(InsufficientHoldingsError) as exc_info:
        async with db_session_factory() as session:
            await service.execute_sell(
                user_id=user.id,
                asset_id=trading_asset.id,
                quantity=Decimal("1.00000000"),
                price=Decimal("100.00000000"),
                session=session,
            )

    assert exc_info.value.error_code == "INSUFFICIENT_HOLDINGS"

    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )

        result = await verification_session.execute(
            select(Transaction).where(
                Transaction.wallet_id == wallet.id,
                Transaction.asset_id == trading_asset.id,
            )
        )
        transactions = result.scalars().all()

        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("10000.00000000")
        assert transactions == []


@pytest.mark.asyncio
async def test_concurrent_buys_prevent_wallet_overdraft(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify concurrent BUY operations cannot overdraw a wallet."""
    user, wallet = trading_user
    service = TradingService()

    async def execute_buy():
        async with db_session_factory() as session:
            return await service.execute_buy(
                user_id=user.id,
                asset_id=trading_asset.id,
                quantity=Decimal("1.00000000"),
                price=Decimal("6000.00000000"),
                session=session,
            )

    results = await asyncio.gather(
        execute_buy(),
        execute_buy(),
        return_exceptions=True,
    )

    successful_trades = [
        result for result in results
        if isinstance(result, Transaction)
    ]
    failed_trades = [
        result for result in results
        if isinstance(result, InsufficientFundsError)
    ]

    assert len(successful_trades) == 1
    assert len(failed_trades) == 1

    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )

        result = await verification_session.execute(
            select(Transaction).where(
                Transaction.wallet_id == wallet.id,
                Transaction.asset_id == trading_asset.id,
            )
        )
        transactions = result.scalars().all()

        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("4000.00000000")
        assert len(transactions) == 1
        assert transactions[0].transaction_type == "BUY"


@pytest.mark.asyncio
async def test_concurrent_sells_prevent_negative_holdings(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify concurrent SELL operations cannot oversell available asset holdings."""
    user, wallet = trading_user
    service = TradingService()
    trading_repo = TradingRepository()

    # Step 1: Establish initial holdings of 10 units via supported BUY execution
    async with db_session_factory() as setup_session:
        setup_buy = await service.execute_buy(
            user_id=user.id,
            asset_id=trading_asset.id,
            quantity=Decimal("10.00000000"),
            price=Decimal("100.00000000"),
            session=setup_session,
        )
        assert setup_buy is not None
        assert setup_buy.quantity == Decimal("10.00000000")

    # Verify baseline database state after setup BUY
    async with db_session_factory() as baseline_session:
        setup_wallet = await baseline_session.get(Wallet, wallet.id)
        assert setup_wallet is not None
        assert setup_wallet.balance == Decimal("9000.00000000")
        setup_holdings = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            baseline_session,
        )
        assert setup_holdings == Decimal("10.00000000")

    # Step 2: Use barrier synchronization and timestamp tracking to coordinate & verify overlap
    barrier = asyncio.Barrier(2)
    start_times: dict[int, float] = {}
    finish_times: dict[int, float] = {}

    async def execute_sell(op_id: int):
        async with db_session_factory() as session:
            # Bounded barrier wait prevents indefinite hangs
            await asyncio.wait_for(barrier.wait(), timeout=5.0)
            start_times[op_id] = asyncio.get_running_loop().time()
            try:
                return await service.execute_sell(
                    user_id=user.id,
                    asset_id=trading_asset.id,
                    quantity=Decimal("8.00000000"),
                    price=Decimal("120.00000000"),
                    session=session,
                )
            finally:
                finish_times[op_id] = asyncio.get_running_loop().time()

    # Step 3: Launch two SELL operations simultaneously with bounded overall timeout
    results = await asyncio.wait_for(
        asyncio.gather(
            execute_sell(1),
            execute_sell(2),
            return_exceptions=True,
        ),
        timeout=10.0,
    )

    # Verify temporal overlap: both operations were in flight simultaneously,
    # proving overlapping coroutine execution intervals (not simultaneous database lock acquisition,
    # as the exclusive wallet row lock mutually serializes them at the database level).
    assert max(start_times.values()) < min(finish_times.values()), (
        "Expected concurrent temporal overlap between coroutine execution intervals"
    )

    # Step 4: Verify exactly one SELL succeeds and the other fails with InsufficientHoldingsError
    assert len(results) == 2

    successful_trades = [
        result for result in results
        if isinstance(result, Transaction)
    ]
    failed_trades = [
        result for result in results
        if isinstance(result, InsufficientHoldingsError)
    ]

    assert len(successful_trades) == 1, (
        f"Expected exactly 1 successful SELL, got {len(successful_trades)}"
    )
    assert len(failed_trades) == 1, (
        f"Expected exactly 1 failed SELL, got {len(failed_trades)}"
    )

    successful_trade = successful_trades[0]
    failed_trade = failed_trades[0]

    assert successful_trade.wallet_id == wallet.id
    assert successful_trade.asset_id == trading_asset.id
    assert successful_trade.transaction_type == "SELL"
    assert successful_trade.quantity == Decimal("8.00000000")
    assert successful_trade.price == Decimal("120.00000000")
    assert successful_trade.total_amount == Decimal("960.00000000")

    assert failed_trade.error_code == "INSUFFICIENT_HOLDINGS"
    assert failed_trade.available == Decimal("2.00000000")
    assert failed_trade.requested == Decimal("8.00000000")

    # Verify no unexpected transaction/session errors or deadlocks occurred
    for result in results:
        assert isinstance(result, (Transaction, InsufficientHoldingsError)), (
            f"Unexpected exception during concurrent SELL execution: {result}"
        )

    # Step 5: Verify final database state
    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )

        # Initial $10,000 - $1,000 (10 BUY @ 100) + $960 (8 SELL @ 120) = $9,960
        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("9960.00000000")

        # Final holdings must be exactly 2 units (10 - 8)
        final_holdings = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            verification_session,
        )
        assert final_holdings == Decimal("2.00000000")

        # Ledger must contain exactly 2 transactions: initial BUY and single successful SELL
        result = await verification_session.execute(
            select(Transaction)
            .where(
                Transaction.wallet_id == wallet.id,
                Transaction.asset_id == trading_asset.id,
            )
            .order_by(Transaction.created_at.asc(), Transaction.id.asc())
        )
        transactions = list(result.scalars().all())

        assert len(transactions) == 2
        assert transactions[0].transaction_type == "BUY"
        assert transactions[0].id == setup_buy.id
        assert transactions[0].quantity == Decimal("10.00000000")
        assert transactions[0].price == Decimal("100.00000000")
        assert transactions[0].total_amount == Decimal("1000.00000000")

        assert transactions[1].transaction_type == "SELL"
        assert transactions[1].id == successful_trade.id
        assert transactions[1].quantity == Decimal("8.00000000")
        assert transactions[1].price == Decimal("120.00000000")
        assert transactions[1].total_amount == Decimal("960.00000000")
