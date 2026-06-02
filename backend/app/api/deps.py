from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.auth_user import AuthUser


async def get_database(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db


def _extract_token(request: Request) -> Optional[str]:
    """Extract session token from Authorization header or X-Session-Token header."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request.headers.get("x-session-token")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthUser:
    """Validate session token and return the authenticated user.

    Raises 401 if token is missing, invalid, expired, or revoked.
    Uses a single joined query for session + user to minimize DB round-trips.
    """
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Single query: load session + user in one round-trip
    result = await db.execute(
        select(AuthSession)
        .options(selectinload(AuthSession.user))
        .where(
            AuthSession.session_token == token,
            AuthSession.revoked_at.is_(None),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token expiry
    if session.expires_at:
        if session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # User already loaded via selectinload
    user = session.user
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[AuthUser]:
    """Optionally authenticate — returns None if no token provided, raises 401 only on invalid token."""
    token = _extract_token(request)
    if not token:
        return None

    # If token is provided, it must be valid
    return await get_current_user(request, db)
