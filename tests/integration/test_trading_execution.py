import asyncio
from decimal import Decimal
from unittest.mock import patch

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
    trading_repo = TradingRepository()

    # Bounded synchronization across coroutines (Python 3.10 compatible)
    ready_event = asyncio.Event()
    counter_lock = asyncio.Lock()
    ready_count = 0

    async def synchronize():
        nonlocal ready_count
        async with counter_lock:
            ready_count += 1
            if ready_count == 2:
                ready_event.set()
        await asyncio.wait_for(ready_event.wait(), timeout=5.0)

    async def execute_buy():
        async with db_session_factory() as session:
            await synchronize()
            return await service.execute_buy(
                user_id=user.id,
                asset_id=trading_asset.id,
                quantity=Decimal("1.00000000"),
                price=Decimal("6000.00000000"),
                session=session,
            )

    results = await asyncio.wait_for(
        asyncio.gather(
            execute_buy(),
            execute_buy(),
            return_exceptions=True,
        ),
        timeout=10.0,
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
        assert transactions[0].id == successful_trades[0].id
        assert transactions[0].wallet_id == wallet.id
        assert transactions[0].asset_id == trading_asset.id
        assert transactions[0].quantity == Decimal("1.00000000")
        assert transactions[0].price == Decimal("6000.00000000")
        assert transactions[0].total_amount == Decimal("6000.00000000")

        holdings = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            verification_session,
        )
        assert holdings == Decimal("1.00000000")


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

    # Step 2: Python 3.10-compatible bounded synchronization across coroutines
    ready_event = asyncio.Event()
    counter_lock = asyncio.Lock()
    ready_count = 0

    async def synchronize():
        nonlocal ready_count
        async with counter_lock:
            ready_count += 1
            if ready_count == 2:
                ready_event.set()
        await asyncio.wait_for(ready_event.wait(), timeout=5.0)

    async def execute_sell():
        async with db_session_factory() as session:
            await synchronize()
            return await service.execute_sell(
                user_id=user.id,
                asset_id=trading_asset.id,
                quantity=Decimal("8.00000000"),
                price=Decimal("120.00000000"),
                session=session,
            )

    # Step 3: Launch two SELL operations simultaneously with bounded overall timeout
    results = await asyncio.wait_for(
        asyncio.gather(
            execute_sell(),
            execute_sell(),
            return_exceptions=True,
        ),
        timeout=10.0,
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

    assert successful_trade.id is not None
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
        assert transactions[0].wallet_id == wallet.id
        assert transactions[0].asset_id == trading_asset.id
        assert transactions[0].quantity == Decimal("10.00000000")
        assert transactions[0].price == Decimal("100.00000000")
        assert transactions[0].total_amount == Decimal("1000.00000000")

        # Verify exactly one SELL record exists in the ledger
        sell_records = [tx for tx in transactions if tx.transaction_type == "SELL"]
        assert len(sell_records) == 1, (
            f"Expected exactly 1 SELL record in ledger, got {len(sell_records)}"
        )
        sell_record = sell_records[0]

        # Verify persisted SELL transaction fields match successful execution
        assert sell_record.id == successful_trade.id
        assert sell_record.wallet_id == wallet.id
        assert sell_record.asset_id == trading_asset.id
        assert sell_record.transaction_type == "SELL"
        assert sell_record.quantity == Decimal("8.00000000")
        assert sell_record.price == Decimal("120.00000000")
        assert sell_record.total_amount == Decimal("960.00000000")

        assert {tx.id for tx in transactions} == {
            setup_buy.id,
            successful_trade.id,
        }


@pytest.mark.asyncio
async def test_concurrent_buy_and_sell_maintains_balance_and_ledger_integrity(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify concurrent BUY and SELL maintain balance and ledger integrity."""
    user, wallet = trading_user
    service = TradingService()
    trading_repo = TradingRepository()

    # Step 1: Establish initial holdings of 5 units via setup BUY execution
    async with db_session_factory() as setup_session:
        setup_buy = await service.execute_buy(
            user_id=user.id,
            asset_id=trading_asset.id,
            quantity=Decimal("5.00000000"),
            price=Decimal("100.00000000"),
            session=setup_session,
        )
        assert setup_buy is not None
        assert setup_buy.quantity == Decimal("5.00000000")

    # Verify baseline database state after setup BUY ($10,000 - $500 = $9,500; 5 units)
    async with db_session_factory() as baseline_session:
        setup_wallet = await baseline_session.get(Wallet, wallet.id)
        assert setup_wallet is not None
        assert setup_wallet.balance == Decimal("9500.00000000")
        setup_holdings = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            baseline_session,
        )
        assert setup_holdings == Decimal("5.00000000")

    # Step 2: Python 3.10-compatible bounded synchronization across coroutines
    ready_event = asyncio.Event()
    counter_lock = asyncio.Lock()
    ready_count = 0

    async def synchronize():
        nonlocal ready_count
        async with counter_lock:
            ready_count += 1
            if ready_count == 2:
                ready_event.set()
        await asyncio.wait_for(ready_event.wait(), timeout=5.0)

    async def execute_concurrent_buy():
        async with db_session_factory() as session:
            await synchronize()
            return await service.execute_buy(
                user_id=user.id,
                asset_id=trading_asset.id,
                quantity=Decimal("2.00000000"),
                price=Decimal("100.00000000"),
                session=session,
            )

    async def execute_concurrent_sell():
        async with db_session_factory() as session:
            await synchronize()
            return await service.execute_sell(
                user_id=user.id,
                asset_id=trading_asset.id,
                quantity=Decimal("3.00000000"),
                price=Decimal("150.00000000"),
                session=session,
            )

    # Step 3: Launch BUY and SELL operations simultaneously with bounded timeout
    results = await asyncio.wait_for(
        asyncio.gather(
            execute_concurrent_buy(),
            execute_concurrent_sell(),
            return_exceptions=True,
        ),
        timeout=10.0,
    )

    # Step 4: Verify both operations completed successfully without unexpected exceptions
    assert len(results) == 2
    for result in results:
        assert isinstance(result, Transaction), (
            f"Unexpected exception during concurrent BUY and SELL execution: {result}"
        )

    buy_trades = [
        r
        for r in results
        if isinstance(r, Transaction) and r.transaction_type == "BUY"
    ]
    sell_trades = [
        r
        for r in results
        if isinstance(r, Transaction) and r.transaction_type == "SELL"
    ]

    assert len(buy_trades) == 1, (
        f"Expected exactly 1 BUY transaction, got {len(buy_trades)}"
    )
    assert len(sell_trades) == 1, (
        f"Expected exactly 1 SELL transaction, got {len(sell_trades)}"
    )

    buy_tx = buy_trades[0]
    sell_tx = sell_trades[0]

    assert buy_tx.wallet_id == wallet.id
    assert buy_tx.asset_id == trading_asset.id
    assert buy_tx.quantity == Decimal("2.00000000")
    assert buy_tx.price == Decimal("100.00000000")
    assert buy_tx.total_amount == Decimal("200.00000000")

    assert sell_tx.wallet_id == wallet.id
    assert sell_tx.asset_id == trading_asset.id
    assert sell_tx.quantity == Decimal("3.00000000")
    assert sell_tx.price == Decimal("150.00000000")
    assert sell_tx.total_amount == Decimal("450.00000000")

    # Step 5: Verify final database state
    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )

        # Initial $10,000 - $500 (setup BUY) - $200 (concurrent BUY)
        # + $450 (concurrent SELL) = $9,750
        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("9750.00000000")

        # Final holdings: 5.0 (setup) + 2.0 (BUY) - 3.0 (SELL) = 4.0 units
        final_holdings = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            verification_session,
        )
        assert final_holdings == Decimal("4.00000000")

        # Ledger must contain exactly 3 transactions: setup BUY,
        # concurrent BUY, and concurrent SELL
        result = await verification_session.execute(
            select(Transaction)
            .where(
                Transaction.wallet_id == wallet.id,
                Transaction.asset_id == trading_asset.id,
            )
            .order_by(Transaction.created_at.asc(), Transaction.id.asc())
        )
        transactions = list(result.scalars().all())

        assert len(transactions) == 3
        assert {tx.id for tx in transactions} == {
            setup_buy.id,
            buy_tx.id,
            sell_tx.id,
        }

        tx_by_id = {tx.id: tx for tx in transactions}
        assert tx_by_id[setup_buy.id].transaction_type == "BUY"
        assert tx_by_id[setup_buy.id].quantity == Decimal("5.00000000")
        assert tx_by_id[setup_buy.id].price == Decimal("100.00000000")
        assert tx_by_id[setup_buy.id].total_amount == Decimal("500.00000000")

        assert tx_by_id[buy_tx.id].transaction_type == "BUY"
        assert tx_by_id[buy_tx.id].quantity == Decimal("2.00000000")
        assert tx_by_id[buy_tx.id].price == Decimal("100.00000000")
        assert tx_by_id[buy_tx.id].total_amount == Decimal("200.00000000")

        assert tx_by_id[sell_tx.id].transaction_type == "SELL"
        assert tx_by_id[sell_tx.id].quantity == Decimal("3.00000000")
        assert tx_by_id[sell_tx.id].price == Decimal("150.00000000")
        assert tx_by_id[sell_tx.id].total_amount == Decimal("450.00000000")


@pytest.mark.asyncio
async def test_buy_rollback_on_ledger_failure_preserves_wallet_and_holdings(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify BUY transaction rolls back wallet debit if ledger creation fails."""
    user, wallet = trading_user
    service = TradingService()
    trading_repo = TradingRepository()

    observed_balance_before_failure: Decimal | None = None

    async def failing_create_transaction(transaction, session):
        nonlocal observed_balance_before_failure
        # Flush the wallet update to the database within the open transaction
        await session.flush()
        in_session_wallet = await session.get(Wallet, wallet.id)
        if in_session_wallet is not None:
            observed_balance_before_failure = in_session_wallet.balance
        raise RuntimeError("Simulated ledger creation failure")

    with patch.object(
        service.trading_repo,
        "create_transaction",
        side_effect=failing_create_transaction,
    ):
        with pytest.raises(
            RuntimeError,
            match="Simulated ledger creation failure",
        ):
            async with db_session_factory() as session:
                await service.execute_buy(
                    user_id=user.id,
                    asset_id=trading_asset.id,
                    quantity=Decimal("2.00000000"),
                    price=Decimal("100.00000000"),
                    session=session,
                )

    # Confirm the wallet update happened before the injected failure
    assert observed_balance_before_failure == Decimal("9800.00000000")

    # Verify using a fresh independent database session:
    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )
        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("10000.00000000")

        holdings = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            verification_session,
        )
        assert holdings == Decimal("0")

        result = await verification_session.execute(
            select(Transaction).where(
                Transaction.wallet_id == wallet.id,
                Transaction.asset_id == trading_asset.id,
            )
        )
        transactions = list(result.scalars().all())
        assert transactions == []


@pytest.mark.asyncio
async def test_sell_rollback_on_ledger_failure_preserves_wallet_and_holdings(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify SELL transaction rolls back wallet credit if ledger creation fails."""
    user, wallet = trading_user
    service = TradingService()
    trading_repo = TradingRepository()

    # Step 1 & 2: Execute real setup BUY of 10 units at $100 ($1,000 cost)
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

    # Step 3: Confirm baseline wallet balance is $9,000 and holdings are 10 units
    async with db_session_factory() as baseline_session:
        baseline_wallet = await baseline_session.get(Wallet, wallet.id)
        assert baseline_wallet is not None
        assert baseline_wallet.balance == Decimal("9000.00000000")
        baseline_holdings = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            baseline_session,
        )
        assert baseline_holdings == Decimal("10.00000000")

    # Step 4: Inject a controlled RuntimeError into trading_repo.create_transaction
    observed_balance_before_failure: Decimal | None = None

    async def failing_create_transaction(transaction, session):
        nonlocal observed_balance_before_failure
        # Flush the wallet update to the database within the open transaction
        await session.flush()
        in_session_wallet = await session.get(Wallet, wallet.id)
        if in_session_wallet is not None:
            observed_balance_before_failure = in_session_wallet.balance
        raise RuntimeError("Simulated ledger creation failure")

    with patch.object(
        service.trading_repo,
        "create_transaction",
        side_effect=failing_create_transaction,
    ):
        with pytest.raises(
            RuntimeError,
            match="Simulated ledger creation failure",
        ):
            async with db_session_factory() as session:
                await service.execute_sell(
                    user_id=user.id,
                    asset_id=trading_asset.id,
                    quantity=Decimal("4.00000000"),
                    price=Decimal("120.00000000"),
                    session=session,
                )

    # Step 6: Confirm the wallet update happened before the injected failure
    # Baseline $9,000 + $480 proceeds = $9,480
    assert observed_balance_before_failure == Decimal("9480.00000000")

    # Step 8: Verify using a fresh independent database session:
    async with db_session_factory() as verification_session:
        updated_wallet = await verification_session.get(
            Wallet,
            wallet.id,
        )
        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("9000.00000000")

        holdings = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            verification_session,
        )
        assert holdings == Decimal("10.00000000")

        result = await verification_session.execute(
            select(Transaction)
            .where(
                Transaction.wallet_id == wallet.id,
                Transaction.asset_id == trading_asset.id,
            )
        )
        transactions = list(result.scalars().all())
        assert len(transactions) == 1
        assert transactions[0].id == setup_buy.id
        assert transactions[0].transaction_type == "BUY"
        assert transactions[0].quantity == Decimal("10.00000000")
        assert transactions[0].price == Decimal("100.00000000")
        assert transactions[0].total_amount == Decimal("1000.00000000")


@pytest.mark.asyncio
async def test_buy_sell_history_and_holdings_lifecycle(
    db_session_factory,
    trading_user,
    trading_asset,
):
    """Verify complete trading lifecycle: BUY -> SELL -> history pagination -> net holdings."""
    user, wallet = trading_user
    service = TradingService()
    trading_repo = TradingRepository()

    # Step 1: BUY 5 units at $100 ($500 cost)
    async with db_session_factory() as session:
        buy_tx = await service.execute_buy(
            user_id=user.id,
            asset_id=trading_asset.id,
            quantity=Decimal("5.00000000"),
            price=Decimal("100.00000000"),
            session=session,
        )
        assert buy_tx.transaction_type == "BUY"
        assert buy_tx.quantity == Decimal("5.00000000")
        assert buy_tx.total_amount == Decimal("500.00000000")

    # Step 2: SELL 2 units at $120 ($240 proceeds)
    async with db_session_factory() as session:
        sell_tx = await service.execute_sell(
            user_id=user.id,
            asset_id=trading_asset.id,
            quantity=Decimal("2.00000000"),
            price=Decimal("120.00000000"),
            session=session,
        )
        assert sell_tx.transaction_type == "SELL"
        assert sell_tx.quantity == Decimal("2.00000000")
        assert sell_tx.total_amount == Decimal("240.00000000")

    # Step 3: Verify wallet balance, transaction history, and net holdings in an independent session
    async with db_session_factory() as verification_session:
        # Initial $10,000 - $500 + $240 = $9,740
        updated_wallet = await verification_session.get(Wallet, wallet.id)
        assert updated_wallet is not None
        assert updated_wallet.balance == Decimal("9740.00000000")

        # Net holdings derived in SQL
        holdings = await trading_repo.get_all_net_holdings(
            wallet.id,
            verification_session,
        )
        assert holdings == {trading_asset.id: Decimal("3.00000000")}

        # Single asset net holdings
        single_holding = await trading_repo.get_net_holdings(
            wallet.id,
            trading_asset.id,
            verification_session,
        )
        assert single_holding == Decimal("3.00000000")

        # History pagination (limit=1, offset=0 returns the most recent transaction: SELL)
        page1 = await trading_repo.get_transaction_history(
            wallet.id,
            verification_session,
            limit=1,
            offset=0,
        )
        assert len(page1) == 1
        tx1, asset1 = page1[0]
        assert tx1.id == sell_tx.id
        assert tx1.transaction_type == "SELL"
        assert asset1.id == trading_asset.id
        assert asset1.symbol == trading_asset.symbol

        # History pagination (limit=1, offset=1 returns the older transaction: BUY)
        page2 = await trading_repo.get_transaction_history(
            wallet.id,
            verification_session,
            limit=1,
            offset=1,
        )
        assert len(page2) == 1
        tx2, asset2 = page2[0]
        assert tx2.id == buy_tx.id
        assert tx2.transaction_type == "BUY"
        assert asset2.id == trading_asset.id

        # Total history count
        total_history = await trading_repo.count_transaction_history(
            wallet.id,
            verification_session,
        )
        assert total_history == 2

        # Filter history by transaction_type=BUY
        buy_history = await trading_repo.get_transaction_history(
            wallet.id,
            verification_session,
            transaction_type="BUY",
        )
        assert len(buy_history) == 1
        assert buy_history[0][0].id == buy_tx.id

        # Filter history by transaction_type=SELL
        sell_history = await trading_repo.get_transaction_history(
            wallet.id,
            verification_session,
            transaction_type="SELL",
        )
        assert len(sell_history) == 1
        assert sell_history[0][0].id == sell_tx.id
