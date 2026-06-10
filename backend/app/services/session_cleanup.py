"""Session cleanup utility — removes expired auth sessions.

Usage:
    python -m app.services.session_cleanup

Or call cleanup_expired_sessions() from a scheduled task.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.auth_session import AuthSession

logger = get_logger("session_cleanup")


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Delete sessions that are expired or revoked.

    Returns the number of deleted sessions.
    """
    now = datetime.now(timezone.utc)

    # Count before delete for logging
    count_stmt = select(func.count(AuthSession.id)).where(
        (AuthSession.expires_at < now) | (AuthSession.revoked_at.is_not(None))
    )
    result = await db.execute(count_stmt)
    expired_count = result.scalar_one()

    if expired_count == 0:
        logger.info("session_cleanup_skipped", reason="no expired sessions")
        return 0

    # Delete expired and revoked sessions
    stmt = delete(AuthSession).where(
        (AuthSession.expires_at < now) | (AuthSession.revoked_at.is_not(None))
    )
    await db.execute(stmt)
    await db.commit()

    logger.info("session_cleanup_complete", deleted_count=expired_count)
    return expired_count


async def _run():
    """Standalone runner for manual invocation."""
    from app.db.session import async_session_factory

    async with async_session_factory() as db:
        count = await cleanup_expired_sessions(db)
        print(f"Cleaned up {count} expired/revoked sessions.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_run())
