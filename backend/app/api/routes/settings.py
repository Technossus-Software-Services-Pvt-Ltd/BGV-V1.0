import json
import os
import secrets
import asyncio
from typing import List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.auth_user import AuthUser
from app.models.integration_config import IntegrationConfig
from app.models.required_document_rule import RequiredDocumentRule
from app.models.enums import IntegrationProvider
from app.schemas.batch import (
    IntegrationConfigResponse,
    IntegrationConfigUpdateRequest,
    GmailStatusResponse,
    DriveConfigRequest,
    FileNamingRuleRequest,
    FileNamingRuleResponse,
    RequiredDocumentChecklistRequest,
    RequiredDocumentRuleResponse,
)
from app.services.settings import FileNamingRuleService
from app.core.config import settings as app_settings
from app.core.logging import get_logger

router = APIRouter(prefix="/settings")
logger = get_logger("api.settings")

# Allow HTTP for localhost OAuth2 redirects during development only
if app_settings.environment == "development":
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
]


# ─── Helper ──────────────────────────────────────────────────────────

async def _get_or_create_config(db: AsyncSession, provider: str) -> IntegrationConfig:
    result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.provider == provider)
    )
    config = result.scalar_one_or_none()
    if not config:
        config = IntegrationConfig(provider=provider, is_enabled=False)
        db.add(config)
        await db.flush()
    return config


# ─── Gmail OAuth2 ────────────────────────────────────────────────────

def _get_google_client_creds() -> tuple[str, str]:
    """Return (client_id, client_secret) from app config or raise."""
    cid = app_settings.google_client_id
    csec = app_settings.google_client_secret
    if not cid or not csec:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth2 not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
        )
    return cid, csec


@router.get("/integrations/gmail/auth-url")
async def get_gmail_auth_url(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Generate Google OAuth2 authorization URL with gmail.modify + drive scopes."""
    client_id, client_secret = _get_google_client_creds()
    config = await _get_or_create_config(db, IntegrationProvider.GMAIL.value)

    redirect_uri = str(request.base_url).rstrip("/") + "/api/v1/settings/integrations/gmail/callback"

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
    )

    state = secrets.token_urlsafe(32)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )

    # Persist state, redirect_uri, and PKCE code_verifier for callback
    existing = json.loads(config.config_json) if config.config_json else {}
    existing["_oauth_state"] = state
    existing["_redirect_uri"] = redirect_uri
    existing["_code_verifier"] = flow.code_verifier
    existing["_oauth_user_id"] = str(_current_user.id)
    config.config_json = json.dumps(existing)
    await db.commit()

    logger.info("gmail_auth_url_generated")
    return {"auth_url": auth_url}


@router.get("/integrations/gmail/callback", response_class=HTMLResponse)
async def gmail_oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth2 redirect callback. Exchanges code for tokens."""
    client_id, client_secret = _get_google_client_creds()
    config = await _get_or_create_config(db, IntegrationProvider.GMAIL.value)

    client_cfg = json.loads(config.config_json) if config.config_json else {}

    # CSRF check
    stored_state = client_cfg.get("_oauth_state")
    if not stored_state or not secrets.compare_digest(state, stored_state):
        return HTMLResponse(
            "<html><body><h2>Error: Invalid state parameter</h2></body></html>",
            status_code=400,
        )

    # Verify this state was issued by a known authenticated user (prevents state fixation)
    stored_user_id = client_cfg.get("_oauth_user_id")
    if not stored_user_id:
        return HTMLResponse(
            "<html><body><h2>Error: OAuth state not bound to a user session</h2></body></html>",
            status_code=400,
        )

    redirect_uri = client_cfg.get("_redirect_uri")
    code_verifier = client_cfg.get("_code_verifier")

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
    )
    flow.code_verifier = code_verifier

    # Token exchange is synchronous — run in thread to avoid blocking
    await asyncio.to_thread(flow.fetch_token, code=code)
    credentials = flow.credentials

    # Serialize to the format expected by google.oauth2.credentials.Credentials.from_authorized_user_info
    token_info = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or GOOGLE_SCOPES),
    }

    config.credentials_json = json.dumps(token_info)
    config.is_enabled = True
    config.last_validated_at = datetime.now(timezone.utc)

    # Fetch connected email
    connected_email = None
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_info(token_info)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        profile = await asyncio.to_thread(
            lambda: service.users().getProfile(userId="me").execute()
        )
        connected_email = profile.get("emailAddress")
    except Exception:
        pass

    # Store email, clean up transient OAuth fields
    client_cfg.pop("_oauth_state", None)
    client_cfg.pop("_redirect_uri", None)
    client_cfg.pop("_code_verifier", None)
    client_cfg.pop("_oauth_user_id", None)
    if connected_email:
        client_cfg["connected_email"] = connected_email
    config.config_json = json.dumps(client_cfg)

    # Also seed drive integration with same credentials so orchestrator works
    drive_config = await _get_or_create_config(db, IntegrationProvider.GOOGLE_DRIVE.value)
    drive_config.credentials_json = config.credentials_json
    drive_config.is_enabled = True
    drive_config.last_validated_at = datetime.now(timezone.utc)

    await db.commit()
    logger.info("gmail_oauth_success", email=connected_email)

    return HTMLResponse("""<!DOCTYPE html>
<html><head><title>Connected</title></head>
<body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center">
<h2 style="color:#16a34a">&#10003; Gmail Connected Successfully</h2>
<p style="color:#6b7280">You can close this window.</p>
</div>
<script>
window.opener && window.opener.postMessage({type:'gmail-oauth-success'},'*');
setTimeout(function(){window.close()},2000);
</script>
</body></html>""")


@router.post("/integrations/gmail/disconnect")
async def disconnect_gmail(db: AsyncSession = Depends(get_db), _current_user: AuthUser = Depends(get_current_user)):
    """Clear stored OAuth tokens (disconnect Gmail & Drive)."""
    gmail = await _get_or_create_config(db, IntegrationProvider.GMAIL.value)
    gmail.credentials_json = None
    gmail.is_enabled = False
    gmail.last_validated_at = None

    # Remove connected_email from config
    if gmail.config_json:
        cfg = json.loads(gmail.config_json)
        cfg.pop("connected_email", None)
        gmail.config_json = json.dumps(cfg)

    # Also clear drive credentials
    drive = await _get_or_create_config(db, IntegrationProvider.GOOGLE_DRIVE.value)
    drive.credentials_json = None
    drive.is_enabled = False
    drive.last_validated_at = None

    await db.commit()
    logger.info("gmail_disconnected")
    return {"status": "disconnected", "message": "Gmail disconnected successfully"}


@router.get("/integrations/gmail/status", response_model=GmailStatusResponse)
async def get_gmail_status(db: AsyncSession = Depends(get_db), _current_user: AuthUser = Depends(get_current_user)):
    """Get current Gmail connection status."""
    config = await _get_or_create_config(db, IntegrationProvider.GMAIL.value)

    has_client = bool(app_settings.google_client_id and app_settings.google_client_secret)
    email = None
    scopes: list[str] = []

    if config.config_json:
        cfg = json.loads(config.config_json)
        email = cfg.get("connected_email")

    connected = bool(config.credentials_json)
    if connected and config.credentials_json:
        creds = json.loads(config.credentials_json)
        scopes = creds.get("scopes", [])

    return GmailStatusResponse(
        connected=connected,
        has_client_config=has_client,
        email=email,
        scopes=scopes,
        is_enabled=config.is_enabled,
        last_validated_at=config.last_validated_at,
    )


# ─── Drive folder config ─────────────────────────────────────────────

@router.put("/integrations/drive/config")
async def update_drive_config(
    body: DriveConfigRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Update Google Drive folder IDs for search and storage."""
    config = await _get_or_create_config(db, IntegrationProvider.GOOGLE_DRIVE.value)
    config.config_json = json.dumps({
        "search_folder_ids": body.search_folder_ids,
        "storage_root_folder_id": body.storage_root_folder_id,
    })
    await db.commit()
    logger.info("drive_config_updated")
    return {"status": "saved", "message": "Drive configuration saved"}


@router.get("/integrations/drive/config")
async def get_drive_config(db: AsyncSession = Depends(get_db), _current_user: AuthUser = Depends(get_current_user)):
    """Get current Drive folder configuration."""
    config = await _get_or_create_config(db, IntegrationProvider.GOOGLE_DRIVE.value)
    if config.config_json:
        return json.loads(config.config_json)
    return {"search_folder_ids": [], "storage_root_folder_id": None}


# ─── Required document checklist ─────────────────────────────────────

@router.get("/required-documents", response_model=List[RequiredDocumentRuleResponse])
async def list_required_documents(db: AsyncSession = Depends(get_db), _current_user: AuthUser = Depends(get_current_user)):
    """Get active required document checklist entries ordered for UI display."""
    result = await db.execute(
        select(RequiredDocumentRule)
        .where(RequiredDocumentRule.is_active.is_(True))
        .order_by(RequiredDocumentRule.sort_order, RequiredDocumentRule.created_at)
    )
    rules = result.scalars().all()

    return [
        RequiredDocumentRuleResponse(
            id=rule.id,
            document_name=rule.document_name,
            category=rule.category,
            is_mandatory=rule.is_mandatory,
            accepted_formats=json.loads(rule.accepted_formats_json or "[]"),
            sort_order=rule.sort_order,
            is_active=rule.is_active,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        for rule in rules
    ]


@router.put("/required-documents", response_model=List[RequiredDocumentRuleResponse])
async def save_required_documents(
    body: RequiredDocumentChecklistRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Replace the required document checklist with the submitted ordered list."""
    existing = await db.execute(select(RequiredDocumentRule))
    for rule in existing.scalars().all():
        await db.delete(rule)

    for idx, item in enumerate(body.items):
        normalized_formats = sorted({fmt.strip().lower() for fmt in item.accepted_formats if fmt.strip()})
        db.add(
            RequiredDocumentRule(
                document_name=item.document_name.strip(),
                category=item.category.strip(),
                is_mandatory=item.is_mandatory,
                accepted_formats_json=json.dumps(normalized_formats),
                sort_order=item.sort_order if item.sort_order is not None else idx,
                is_active=item.is_active,
            )
        )

    await db.commit()

    refreshed = await db.execute(
        select(RequiredDocumentRule)
        .where(RequiredDocumentRule.is_active.is_(True))
        .order_by(RequiredDocumentRule.sort_order, RequiredDocumentRule.created_at)
    )
    rules = refreshed.scalars().all()

    logger.info("required_document_checklist_saved", total=len(rules))

    return [
        RequiredDocumentRuleResponse(
            id=rule.id,
            document_name=rule.document_name,
            category=rule.category,
            is_mandatory=rule.is_mandatory,
            accepted_formats=json.loads(rule.accepted_formats_json or "[]"),
            sort_order=rule.sort_order,
            is_active=rule.is_active,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        for rule in rules
    ]


@router.get("/file-naming", response_model=FileNamingRuleResponse)
async def get_file_naming_rule(db: AsyncSession = Depends(get_db), _current_user: AuthUser = Depends(get_current_user)):
    """Get active file naming rule configuration for UI display and editing."""
    rule = await FileNamingRuleService.get_active_rule(db)
    return FileNamingRuleResponse(
        id=rule.id,
        folder_structure_pattern=rule.folder_structure_pattern,
        file_rename_pattern=rule.file_rename_pattern,
        example_output=rule.example_output,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.put("/file-naming", response_model=FileNamingRuleResponse)
async def save_file_naming_rule(
    body: FileNamingRuleRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Save active file naming rule configuration."""
    folder_pattern = body.folder_structure_pattern.strip()
    file_pattern = body.file_rename_pattern.strip()

    if not folder_pattern or not file_pattern:
        raise HTTPException(status_code=400, detail="Both file naming patterns are required")

    saved = await FileNamingRuleService.save_rule(
        db=db,
        folder_structure_pattern=folder_pattern,
        file_rename_pattern=file_pattern,
    )

    logger.info("file_naming_rule_saved", rule_id=saved.id)

    return FileNamingRuleResponse(
        id=saved.id,
        folder_structure_pattern=saved.folder_structure_pattern,
        file_rename_pattern=saved.file_rename_pattern,
        example_output=saved.example_output,
        is_active=saved.is_active,
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


# ─── Legacy generic endpoints (kept for compatibility) ───────────────

@router.get("/integrations", response_model=List[IntegrationConfigResponse])
async def list_integrations(db: AsyncSession = Depends(get_db), _current_user: AuthUser = Depends(get_current_user)):
    """List all integration configurations."""
    result = await db.execute(select(IntegrationConfig).order_by(IntegrationConfig.provider))
    configs = result.scalars().all()

    existing_providers = {c.provider for c in configs}
    for provider in IntegrationProvider:
        if provider.value not in existing_providers:
            new_config = IntegrationConfig(provider=provider.value, is_enabled=False)
            db.add(new_config)
            configs.append(new_config)

    await db.flush()

    return [
        IntegrationConfigResponse(
            id=c.id,
            provider=c.provider,
            is_enabled=c.is_enabled,
            has_credentials=bool(c.credentials_json),
            config_json=c.config_json,
            last_validated_at=c.last_validated_at,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ]


@router.put("/integrations/{provider}", response_model=IntegrationConfigResponse)
async def update_integration(
    provider: str,
    request: IntegrationConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Update an integration's configuration."""
    valid_providers = {p.value for p in IntegrationProvider}
    if provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}")

    config = await _get_or_create_config(db, provider)

    if request.is_enabled is not None:
        config.is_enabled = request.is_enabled
    if request.credentials_json is not None:
        try:
            json.loads(request.credentials_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="credentials_json must be valid JSON")
        config.credentials_json = request.credentials_json
    if request.config_json is not None:
        try:
            json.loads(request.config_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="config_json must be valid JSON")
        config.config_json = request.config_json

    await db.commit()
    logger.info("integration_updated", provider=provider, enabled=config.is_enabled)

    return IntegrationConfigResponse(
        id=config.id,
        provider=config.provider,
        is_enabled=config.is_enabled,
        has_credentials=bool(config.credentials_json),
        config_json=config.config_json,
        last_validated_at=config.last_validated_at,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/integrations/{provider}/validate")
async def validate_integration(provider: str, db: AsyncSession = Depends(get_db), _current_user: AuthUser = Depends(get_current_user)):
    """Test that an integration's credentials are valid."""
    result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.provider == provider)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"Integration '{provider}' not configured")

    if not config.credentials_json:
        raise HTTPException(status_code=400, detail="No credentials configured")

    try:
        if provider == IntegrationProvider.GMAIL.value:
            from app.services.integrations.gmail_scanner import GmailScanner
            scanner = GmailScanner(config.credentials_json)
            await asyncio.to_thread(
                lambda: scanner._service.users().messages().list(userId="me", maxResults=1).execute()
            )

        elif provider == IntegrationProvider.GOOGLE_DRIVE.value:
            from app.services.integrations.drive_service import GoogleDriveService
            service = GoogleDriveService(config.credentials_json, config.config_json)
            await asyncio.to_thread(
                lambda: service._service.files().list(pageSize=1).execute()
            )

        config.last_validated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "valid", "message": f"{provider} credentials validated successfully"}

    except Exception as e:
        return {"status": "invalid", "message": str(e)}
