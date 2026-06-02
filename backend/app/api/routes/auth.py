import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import or_, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.auth_user import AuthUser
from app.models.oauth_state import OAuthState

router = APIRouter()

_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
_REVOKE_URI = "https://oauth2.googleapis.com/revoke"


class GoogleAuthStartResponse(BaseModel):
    success: bool
    oauth_url: str
    state: str


class GoogleAuthCallbackRequest(BaseModel):
    code: str
    state: str


class AuthenticatedUser(BaseModel):
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    google_id: Optional[str] = None


class GoogleAuthCallbackResponse(BaseModel):
    success: bool
    user: AuthenticatedUser
    session_token: str


class LogoutResponse(BaseModel):
    success: bool
    message: str


def _extract_session_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return request.headers.get("x-session-token")


def _resolve_redirect_uri(request: Optional[Request], redirect_uri: Optional[str]) -> str:
    if redirect_uri:
        return redirect_uri

    if request:
        origin = request.headers.get("origin")
        if not origin:
            referer = request.headers.get("referer")
            if referer:
                parsed = urlparse(referer)
                if parsed.scheme and parsed.netloc:
                    origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin and (origin.startswith("http://") or origin.startswith("https://")):
            return f"{origin.rstrip('/')}/auth/callback"

    return settings.google_redirect_uri


def _validate_oauth_config() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )


async def _prune_expired_states(db: AsyncSession) -> None:
    """Remove expired OAuth states from the database."""
    now = datetime.now(timezone.utc)
    await db.execute(delete(OAuthState).where(OAuthState.expires_at <= now))


@router.get(
    "/auth/google/start",
    response_model=GoogleAuthStartResponse,
    status_code=status.HTTP_200_OK,
)
async def google_auth_start(
    request: Request,
    redirect_uri: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    _validate_oauth_config()
    await _prune_expired_states(db)

    state = str(uuid.uuid4())
    resolved_redirect_uri = _resolve_redirect_uri(request, redirect_uri)

    # Store state in database (safe across multiple workers)
    oauth_state = OAuthState(
        state=state,
        redirect_uri=resolved_redirect_uri,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(oauth_state)
    await db.flush()

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": resolved_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account consent",
    }

    return GoogleAuthStartResponse(
        success=True,
        oauth_url=f"{_AUTH_URI}?{urlencode(params)}",
        state=state,
    )


@router.post(
    "/auth/google/callback",
    response_model=GoogleAuthCallbackResponse,
    status_code=status.HTTP_200_OK,
)
async def google_auth_callback(payload: GoogleAuthCallbackRequest, db: AsyncSession = Depends(get_db)):
    _validate_oauth_config()
    await _prune_expired_states(db)

    # Look up state from database (works across multiple workers)
    result = await db.execute(
        select(OAuthState).where(OAuthState.state == payload.state)
    )
    oauth_state = result.scalar_one_or_none()

    if not oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state. Please sign in again.",
        )

    # Check expiry
    if oauth_state.expires_at < datetime.now(timezone.utc):
        await db.delete(oauth_state)
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state expired. Please sign in again.",
        )

    redirect_uri = oauth_state.redirect_uri

    # Consume the state (single-use)
    await db.delete(oauth_state)
    await db.flush()

    token_data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": payload.code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token_response = await client.post(_TOKEN_URI, data=token_data)
            token_response.raise_for_status()
            token_payload = token_response.json()

            access_token = token_payload.get("access_token")
            refresh_token = token_payload.get("refresh_token")
            token_type = token_payload.get("token_type")
            expires_in = token_payload.get("expires_in")
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google OAuth token exchange did not return an access token.",
                )

            user_response = await client.get(
                _USERINFO_URI,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_response.raise_for_status()
            user_payload = user_response.json()
    except HTTPException:
        raise
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth request failed. Please try again.",
        )

    email = user_payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google profile did not include an email address.",
        )

    session_token = str(uuid.uuid4())
    result = await db.execute(
        select(AuthUser).where(
            or_(AuthUser.google_id == user_payload.get("id"), AuthUser.email == email)
        )
    )
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_in) if expires_in else None

    if user is None:
        user = AuthUser(
            email=email,
            name=user_payload.get("name"),
            picture=user_payload.get("picture"),
            google_id=user_payload.get("id"),
            auth_provider="google",
            is_active=True,
            last_login_at=now,
        )
        db.add(user)
        await db.flush()
    else:
        user.email = email
        user.name = user_payload.get("name")
        user.picture = user_payload.get("picture")
        user.google_id = user_payload.get("id")
        user.is_active = True
        user.last_login_at = now
        await db.flush()

    session = AuthSession(
        user_id=user.id,
        session_token=session_token,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=token_type,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    return GoogleAuthCallbackResponse(
        success=True,
        user=AuthenticatedUser(
            email=email,
            name=user_payload.get("name"),
            picture=user_payload.get("picture"),
            google_id=user_payload.get("id"),
        ),
        session_token=session_token,
    )


@router.post(
    "/auth/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    session_token = _extract_session_token(request)
    if not session_token:
        return LogoutResponse(success=True, message="Signed out successfully")

    result = await db.execute(
        select(AuthSession).where(AuthSession.session_token == session_token)
    )
    session = result.scalar_one_or_none()
    if not session:
        return LogoutResponse(success=True, message="Signed out successfully")

    access_token = session.access_token
    if access_token:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(_REVOKE_URI, data={"token": access_token})
        except httpx.HTTPError:
            # Local logout still succeeds even if Google revoke is temporarily unavailable.
            pass

    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    return LogoutResponse(success=True, message="Signed out successfully")
