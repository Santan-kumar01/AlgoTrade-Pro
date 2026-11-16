from uuid import UUID
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Wallet


class WalletRepository:
    """Database operations for trading wallets."""

    async def get_wallet_for_update(
        self,
        wallet_id: UUID,
        session: AsyncSession,
    ) -> Wallet | None:
        """Retrieve and lock a wallet row for an atomic trade."""

        statement = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .with_for_update()
        )

        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def get_wallet_for_user_update(
        self,
        user_id: UUID,
        session: AsyncSession,
    ) -> Wallet | None:
        """Retrieve and lock a user's wallet for an atomic trade."""

        statement = (
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )

        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def get_wallet_by_user_id(
        self,
        user_id: UUID,
        session: AsyncSession,
    ) -> Wallet | None:
        """Retrieve a wallet belonging to a specific user."""

        statement = select(Wallet).where(
            Wallet.user_id == user_id
        )

        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def update_balance(
        self,
        wallet: Wallet,
        new_balance: Decimal,
    ) -> Wallet:
        """Update wallet balance within the caller's transaction."""

        wallet.balance = new_balance
        return wallet
