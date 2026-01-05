"""Account repository for database operations."""

from datetime import UTC, datetime

from sqlmodel import select

from claude_code_proxy.db.engine import get_session
from claude_code_proxy.db.models import Account


class AccountRepository:
    """Repository for Account operations."""

    async def create(
        self,
        name: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        email: str | None = None,
        display_name: str | None = None,
    ) -> Account:
        """Create a new account."""
        async with get_session() as session:
            account = Account(
                name=name,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=expires_at,
                email=email,
                display_name=display_name,
            )
            session.add(account)
            await session.commit()
            await session.refresh(account)
            return account

    async def get(self, name: str) -> Account | None:
        """Get an account by name."""
        async with get_session() as session:
            result = await session.execute(select(Account).where(Account.name == name))
            return result.scalar_one_or_none()

    async def list_all(self) -> list[Account]:
        """List all accounts."""
        async with get_session() as session:
            result = await session.execute(select(Account))
            return list(result.scalars().all())

    async def delete(self, name: str) -> bool:
        """Delete an account. Returns True if deleted, False if not found."""
        async with get_session() as session:
            result = await session.execute(select(Account).where(Account.name == name))
            account = result.scalar_one_or_none()
            if account:
                await session.delete(account)
                await session.commit()
                return True
            return False

    async def update_tokens(
        self,
        name: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> Account | None:
        """Update account tokens."""
        async with get_session() as session:
            result = await session.execute(select(Account).where(Account.name == name))
            account = result.scalar_one_or_none()
            if account:
                account.access_token = access_token
                account.refresh_token = refresh_token
                account.token_expires_at = expires_at
                account.updated_at = datetime.now(UTC)
                session.add(account)
                await session.commit()
                await session.refresh(account)
            return account

    async def mark_used(self, name: str) -> None:
        """Mark an account as used (update last_used_at and increment count)."""
        async with get_session() as session:
            result = await session.execute(select(Account).where(Account.name == name))
            account = result.scalar_one_or_none()
            if account:
                account.last_used_at = datetime.now(UTC)
                account.use_count += 1
                session.add(account)
                await session.commit()
