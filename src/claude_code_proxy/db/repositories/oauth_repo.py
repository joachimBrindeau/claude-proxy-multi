"""OAuth flow repository for database operations."""

from datetime import UTC, datetime, timedelta

from sqlmodel import select

from claude_code_proxy.db.engine import get_session
from claude_code_proxy.db.models import OAuthFlow


class OAuthFlowRepository:
    """Repository for OAuth flow operations."""

    async def create(
        self,
        state: str,
        account_name: str,
        code_challenge: str,
        redirect_uri: str,
        ttl_seconds: int = 3600,
    ) -> OAuthFlow:
        """Create a new OAuth flow."""
        now = datetime.now(UTC)
        async with get_session() as session:
            flow = OAuthFlow(
                state=state,
                account_name=account_name,
                code_challenge=code_challenge,
                redirect_uri=redirect_uri,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
            session.add(flow)
            await session.commit()
            await session.refresh(flow)
            return flow

    async def get_valid(self, state: str) -> OAuthFlow | None:
        """Get a flow if it exists and hasn't expired."""
        async with get_session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                select(OAuthFlow).where(
                    OAuthFlow.state == state,
                    OAuthFlow.expires_at > now,
                )
            )
            return result.scalar_one_or_none()

    async def delete(self, state: str) -> bool:
        """Delete a flow. Returns True if deleted."""
        async with get_session() as session:
            result = await session.execute(
                select(OAuthFlow).where(OAuthFlow.state == state)
            )
            flow = result.scalar_one_or_none()
            if flow:
                await session.delete(flow)
                await session.commit()
                return True
            return False

    async def cleanup_expired(self) -> int:
        """Delete all expired flows. Returns count deleted."""
        async with get_session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                select(OAuthFlow).where(OAuthFlow.expires_at <= now)
            )
            expired = list(result.scalars().all())
            for flow in expired:
                await session.delete(flow)
            await session.commit()
            return len(expired)

    async def get_pending_account_names(self) -> list[str]:
        """Get list of account names with pending (non-expired) flows."""
        async with get_session() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                select(OAuthFlow.account_name).where(OAuthFlow.expires_at > now)
            )
            return list(result.scalars().all())
