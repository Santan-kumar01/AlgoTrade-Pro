import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.core.exceptions import (
    InsufficientFundsError,
    InsufficientHoldingsError,
)
from src.models import Transaction, Wallet
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
