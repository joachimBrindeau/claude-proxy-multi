"""Rate limit repository for database operations."""

from datetime import UTC, datetime

from sqlmodel import select

from claude_code_proxy.db.engine import get_session
from claude_code_proxy.db.models import RateLimit


class RateLimitRepository:
    """Repository for rate limit operations."""

    async def mark_limited(
        self,
        account_name: str,
        resets_at: datetime,
        triggered_by: str | None = None,
    ) -> RateLimit:
        """Mark an account as rate limited (upserts - updates if exists, creates if not)."""
        async with get_session() as session:
            # Check if exists and update, or create new
            result = await session.execute(
                select(RateLimit).where(RateLimit.account_name == account_name)
            )
            rate_limit = result.scalar_one_or_none()

            if rate_limit:
                rate_limit.limited_at = datetime.now(UTC)
                rate_limit.resets_at = resets_at
                rate_limit.triggered_by = triggered_by
            else:
                rate_limit = RateLimit(
                    account_name=account_name,
                    limited_at=datetime.now(UTC),
                    resets_at=resets_at,
                    triggered_by=triggered_by,
                )
                session.add(rate_limit)

            await session.commit()
            await session.refresh(rate_limit)
            return rate_limit

    async def is_limited(self, account_name: str) -> bool:
        """Check if an account is currently rate limited (resets_at > now)."""
        async with get_session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                select(RateLimit).where(
                    RateLimit.account_name == account_name,
                    RateLimit.resets_at > now,
                )
            )
            return result.scalar_one_or_none() is not None

    async def get(self, account_name: str) -> RateLimit | None:
        """Get rate limit info for an account."""
        async with get_session() as session:
            result = await session.execute(
                select(RateLimit).where(RateLimit.account_name == account_name)
            )
            return result.scalar_one_or_none()

    async def clear(self, account_name: str) -> bool:
        """Clear rate limit for an account. Returns True if deleted, False if not found."""
        async with get_session() as session:
            result = await session.execute(
                select(RateLimit).where(RateLimit.account_name == account_name)
            )
            rate_limit = result.scalar_one_or_none()
            if rate_limit:
                await session.delete(rate_limit)
                await session.commit()
                return True
            return False

    async def get_all_limited(self) -> list[RateLimit]:
        """Get all currently rate-limited accounts (only those not expired)."""
        async with get_session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                select(RateLimit).where(RateLimit.resets_at > now)
            )
            return list(result.scalars().all())

    async def cleanup_expired(self) -> int:
        """Delete expired rate limit records. Returns count deleted."""
        async with get_session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                select(RateLimit).where(RateLimit.resets_at <= now)
            )
            expired = list(result.scalars().all())
            for rl in expired:
                await session.delete(rl)
            await session.commit()
            return len(expired)
