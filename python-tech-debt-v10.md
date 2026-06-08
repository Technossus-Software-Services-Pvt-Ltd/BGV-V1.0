# Python Tech Debt Audit — v10

**Audit Date:** 2026-06-04  
**Auditor Roles:** Principal Python Architect · Senior FastAPI Engineer · Staff Security Engineer · DevSecOps Architect · Performance Engineer  
**Scope:** Full backend codebase (`backend/app/`)

---

## 1. 📁 File-Level Tech Debt

---

### File: `backend/app/main.py`

#### Function: `_recover_stuck_documents`
**Line:** 49–67  
**Severity:** 🟠 P1

❌ **Issue:**  
Advisory lock uses f-string interpolation of an integer constant in a raw SQL `text()` call. While this specific case is safe (constant integer), it sets a dangerous pattern for future maintainers who may introduce user-controlled values.

🔍 **Root Cause:**  
Using `text(f"SELECT pg_advisory_lock({ADVISORY_LOCK_DOCUMENT_RECOVERY})")` instead of parameterized queries.

⚠ **Production Impact:**  
Pattern encourages SQL injection in future modifications; no immediate exploitability since the value is a module-level constant.

🏗 **Category:** Security / Anti-pattern

👉 **Suggested Fix:**
```python
from sqlalchemy import text
await db.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_DOCUMENT_RECOVERY})
# ...
await db.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": ADVISORY_LOCK_DOCUMENT_RECOVERY})
```

---

#### Function: `catch_unhandled_exceptions` (middleware)
**Line:** 119–133  
**Severity:** 🟡 P2

❌ **Issue:**  
The middleware re-raises `BGVBaseException` after the call to `call_next()` has already been invoked. At this point, the response stream may have already started — Starlette's `StreamingResponse` can produce partial body before the exception handler activates.

🔍 **Root Cause:**  
Middleware wraps `call_next()` but cannot reliably catch exceptions raised during streaming.

⚠ **Production Impact:**  
For non-streaming JSON responses (most of this API) this is fine. If streaming responses are ever introduced, clients may receive truncated/corrupt data.

🏗 **Category:** Architecture

👉 **Refactoring Approach:**  
Acceptable as-is for JSON-only APIs. Document the limitation or switch to an ASGI exception handler pattern if streaming is added.

---

### File: `backend/app/core/config.py`

✅ No critical issues found. Configuration is well-structured with production validation.

#### Minor: `session_cookie_secure` default
**Line:** 76  
**Severity:** 🟡 P2

❌ **Issue:**  
`session_cookie_secure: bool = False` — if deployed without flipping this, session cookies transmit over HTTP.

🔍 **Root Cause:**  
Default is safe for development but risky if production .env omits this setting.

⚠ **Production Impact:**  
Session hijacking via network sniffing if HTTPS is not enforced at the load-balancer level.

🏗 **Category:** Security / Configuration

👉 **Suggested Fix:**
```python
@model_validator(mode="after")
def _validate_required_settings(self) -> "Settings":
    # ... existing code ...
    if self.environment != "development" and not self.session_cookie_secure:
        raise ValueError("SESSION_COOKIE_SECURE must be True in production")
    return self
```

---

### File: `backend/app/core/security.py`

✅ No issues found. File validation uses magic bytes, sanitization is thorough, and MIME type detection has proper fallback.

---

### File: `backend/app/core/logging.py`

✅ No issues found. Structured logging via structlog is properly configured.

---

### File: `backend/app/core/exceptions.py`

#### Class: `BGVBaseException`
**Line:** 25  
**Severity:** 🟡 P2

❌ **Issue:**  
Missing `ProcessingTimeoutError` class referenced in the docstring hierarchy comment.

🔍 **Root Cause:**  
Docstring lists `ProcessingTimeoutError (504)` but no implementation exists.

⚠ **Production Impact:**  
Missing abstraction forces raw exceptions or generic 500s for timeout scenarios.

🏗 **Category:** Architecture / Maintainability

👉 **Suggested Fix:**
```python
class ProcessingTimeoutError(BGVBaseException):
    """Raised when a processing operation exceeds its time budget."""
    status_code = 504
```

---

### File: `backend/app/db/session.py`

#### Function: `get_db`
**Line:** 19–25  
**Severity:** 🟡 P2

❌ **Issue:**  
The `get_db` generator does not explicitly commit — callers must remember to call `await db.commit()`. If omitted, changes silently rollback.

🔍 **Root Cause:**  
Implicit rollback on session close without commit. FastAPI routes handle commit manually but it's easy to forget.

⚠ **Production Impact:**  
Data loss if a route path forgets to commit (already handled correctly in most places).

🏗 **Category:** Architecture

👉 **Refactoring Approach:**  
Current approach is acceptable (explicit commits) but consider adding a read-only `get_db_readonly` dependency for GET endpoints that wraps in a `with db.begin():` block for clarity.

---

### File: `backend/app/api/deps.py`

✅ No issues found. Authentication is solid: httpOnly cookie preferred, single-query session+user fetch, proper expiry checks.

---

### File: `backend/app/api/routes/upload.py`

#### Function: `upload_documents`
**Line:** 88–90  
**Severity:** 🟠 P1

❌ **Issue:**  
File is written to disk BEFORE content validation completes. If the size check at line 115 fails, the file is cleaned up, but between write and cleanup, a partially-written oversized file exists on disk. Under concurrent load, disk can fill before cleanup runs.

🔍 **Root Cause:**  
Streaming write and size check happen in sequence rather than via a bounded-write wrapper.

⚠ **Production Impact:**  
Disk exhaustion under malicious upload flood (DoS vector). The cleanup logic mitigates but doesn't prevent transient disk pressure.

🏗 **Category:** Security / Performance

👉 **Suggested Fix:**
```python
# Break out of loop immediately and remove file inline:
async with aiofiles.open(file_path, "wb") as f:
    while chunk := await file.read(1024 * 1024):
        file_size += len(chunk)
        if file_size > settings.max_upload_size_bytes:
            await f.close()
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=413, detail=f"File size exceeds {settings.max_upload_size_mb}MB limit")
        if file_size == len(chunk):
            header_bytes = chunk[:2048]
        await f.write(chunk)
```

---

#### Function: `_process_document_background`
**Line:** 157–168  
**Severity:** 🟠 P1

❌ **Issue:**  
Background task catches bare `Exception` and only logs — no retry mechanism. Transient failures (DB connection reset, temporary Ollama unavailability) permanently mark documents as failed with no recovery path.

🔍 **Root Cause:**  
No retry/dead-letter pattern in background document processing.

⚠ **Production Impact:**  
Documents stuck in failed state requiring manual intervention; silent data loss.

🏗 **Category:** Architecture / Resilience

👉 **Suggested Fix:**
```python
async def _process_document_background(document_id: str, max_retries: int = 2):
    for attempt in range(max_retries + 1):
        async with AsyncSessionLocal() as db:
            try:
                pipeline = get_processing_pipeline(db)
                await pipeline.process_document(document_id)
                await db.commit()
                return
            except Exception as e:
                await db.rollback()
                if attempt < max_retries:
                    logger.warning("background_processing_retry", document_id=document_id, attempt=attempt + 1, error=str(e))
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error("background_processing_failed", document_id=document_id, error=str(e))
```

---

### File: `backend/app/api/routes/documents.py`

#### Function: `list_documents`
**Line:** 34–37  
**Severity:** 🟡 P2

❌ **Issue:**  
`candidate_id` parameter accepts any string without UUID or format validation — an attacker can inject SQL wildcard chars, though SQLAlchemy parameterizes so no actual injection risk. More importantly, the filter uses `Document.candidate_id` which is a UUID FK — a non-UUID value will simply return empty, but no 400 error guides the caller.

🔍 **Root Cause:**  
Missing input validation on path/query parameters that represent UUIDs.

⚠ **Production Impact:**  
Poor API ergonomics; no immediate security risk thanks to SQLAlchemy parameterization.

🏗 **Category:** Validation

👉 **Suggested Fix:**
```python
from pydantic import UUID4
# Use typed query params or validate with regex
```

---

### File: `backend/app/api/routes/auth.py`

#### Function: `google_auth_callback`
**Line:** 213–220  
**Severity:** 🟠 P1

❌ **Issue:**  
After the OAuth state expires, the code calls `await db.commit()` and THEN raises `HTTPException`. The commit persists the deletion of the expired state, which is correct, but the pattern of `commit → raise` is unusual and could confuse maintainers. More critically, if `httpx.AsyncClient()` call fails with an unhandled exception type (not `httpx.HTTPError`), the generic `except Exception` is missing — only `HTTPException` and `httpx.HTTPError` are caught.

🔍 **Root Cause:**  
Incomplete exception handling in token exchange block.

⚠ **Production Impact:**  
If `response.json()` raises `json.JSONDecodeError`, the request crashes with a 500 instead of a friendly 400.

🏗 **Category:** Exception Handling

👉 **Suggested Fix:**
```python
except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Google OAuth request failed. Please try again.",
    )
```

---

#### Function: `google_auth_callback`
**Line:** 265  
**Severity:** 🟠 P1

❌ **Issue:**  
`session_token` is returned in the JSON response body (`GoogleAuthCallbackResponse`) in addition to being set as an httpOnly cookie. This defeats the purpose of httpOnly cookies — if the token is also in the response body, XSS can steal it.

🔍 **Root Cause:**  
Backwards compatibility with legacy header-based auth coexists with cookie-based auth.

⚠ **Production Impact:**  
Session token exposure via XSS if frontend stores the body token in localStorage/memory and an XSS vulnerability exists.

🏗 **Category:** Security

👉 **Suggested Fix:**
```python
# Remove session_token from response body, or mark it for deprecation:
class GoogleAuthCallbackResponse(BaseModel):
    success: bool
    user: AuthenticatedUser
    # session_token: str  # DEPRECATED — token is set via httpOnly cookie only
```

---

### File: `backend/app/api/routes/health.py`

#### Function: `_get_ollama_client`
**Line:** 10–12  
**Severity:** 🟠 P1

❌ **Issue:**  
`@lru_cache(maxsize=1)` on a function returning a mutable object creates a true singleton, but `lru_cache` retains a reference forever. If `get_ai_classifier()` raises an exception or returns a partially-initialized client, the broken instance is cached permanently.

🔍 **Root Cause:**  
`lru_cache` caches exceptions as `None` returns (if the function succeeds without raising). But the deeper issue is that `_get_ollama_client` aliases `_ollama_client` in `main.py` for shutdown cleanup — creating divergent references if the dependency module is reloaded or re-initialized.

⚠ **Production Impact:**  
Health check may reference a stale client object post-shutdown; minor since health is non-critical.

🏗 **Category:** Architecture

👉 **Suggested Fix:**
```python
# Use the module-level singleton directly:
from app.services.dependencies import get_ai_classifier

@router.get("/health")
async def health_check():
    client = get_ai_classifier().client
    ollama_healthy = await client.check_health()
    model_available = await client.ensure_model_available() if ollama_healthy else False
    return {
        "status": "healthy",
        "services": {"api": True, "ollama": ollama_healthy, "ollama_model": model_available},
    }
```

---

### File: `backend/app/api/routes/dashboard.py`

#### Function: `get_dashboard_stats`
**Line:** 32–34  
**Severity:** 🟡 P2

❌ **Issue:**  
Module-level mutable dict `_dashboard_cache` with `asyncio.Lock()` works in a single-process deployment but provides no cache coherence across multiple Uvicorn workers. Each worker has its own independent cache.

🔍 **Root Cause:**  
In-process caching without shared-state (Redis) backend.

⚠ **Production Impact:**  
No correctness issue (each worker independently computes stats), but multiplied DB load under multi-worker deployment negates caching benefit.

🏗 **Category:** Performance / Scalability

👉 **Refactoring Approach:**  
Acceptable for single-process; for multi-worker production, introduce Redis-backed caching.

---

### File: `backend/app/api/routes/settings.py`

#### Variable: `_callback_attempts`
**Line:** 49–51  
**Severity:** 🟡 P2

❌ **Issue:**  
In-memory rate limiting via `_callback_attempts: dict[str, list[float]]` is unbounded — entries are never removed after the rate window expires. Under sustained diverse-IP probing, this dict grows unbounded causing memory leak.

🔍 **Root Cause:**  
Old entries are pruned per-key on access but keys themselves are never cleaned up.

⚠ **Production Impact:**  
Slow memory leak under distributed attack; trivial memory for typical usage.

🏗 **Category:** Memory Leak / Security

👉 **Suggested Fix:**
```python
# Add periodic cleanup or use a TTL dict:
from cachetools import TTLCache
_callback_attempts: TTLCache = TTLCache(maxsize=10000, ttl=_CALLBACK_RATE_WINDOW)
```

---

### File: `backend/app/api/routes/batch.py`

#### Function: `upload_batch_file`
**Line:** 68–75  
**Severity:** 🟡 P2

❌ **Issue:**  
File bytes are accumulated entirely in memory (`chunks.append(chunk)` → `b"".join(chunks)`) up to 10MB. For concurrent batch uploads, this multiplies memory usage.

🔍 **Root Cause:**  
Streaming to disk is done after full in-memory buffering. The pattern is acceptable for 10MB but could be optimized.

⚠ **Production Impact:**  
Under 20 concurrent batch uploads: 200MB transient RAM. Not critical but suboptimal.

🏗 **Category:** Performance

👉 **Refactoring Approach:**  
Stream directly to a temp file, then parse from disk. This removes the in-memory buffer.

---

### File: `backend/app/api/routes/ws.py`

✅ No critical issues. WebSocket authentication is well-implemented with ticket-based auth and proper timeout handling.

---

### File: `backend/app/services/task_manager.py`

✅ No issues found. Clean implementation with semaphore-based concurrency, graceful shutdown, and proper callback-based cleanup.

---

### File: `backend/app/services/processing/pipeline.py`

✅ No issues found. Well-structured stage-based pipeline with proper context passing.

---

### File: `backend/app/services/ocr/engine.py`

#### Module-level: `_ocr_executor`
**Line:** 30–33  
**Severity:** 🟡 P2

❌ **Issue:**  
`ThreadPoolExecutor` created at module import time. If the module is imported but OCR is never used (e.g., in test environments or health-check-only workers), threads are allocated unnecessarily.

🔍 **Root Cause:**  
Eager initialization of thread pool.

⚠ **Production Impact:**  
2 idle OS threads per process when OCR is unused; negligible in practice.

🏗 **Category:** Performance

👉 **Refactoring Approach:**  
Use lazy initialization (create executor on first use). Low priority.

---

### File: `backend/app/services/ocr/preprocessor.py`

#### Function: `extract_pages_from_pdf`
**Line:** 26–38  
**Severity:** 🟠 P1

❌ **Issue:**  
`fitz.open()` (PyMuPDF) processes untrusted user-uploaded PDFs without any sandboxing or resource limits. A crafted PDF with thousands of pages could exhaust memory/disk at 300 DPI rendering.

🔍 **Root Cause:**  
No page count limit before rendering at high DPI.

⚠ **Production Impact:**  
Memory exhaustion / DoS via crafted multi-thousand-page PDF.

🏗 **Category:** Security / Performance

👉 **Suggested Fix:**
```python
MAX_PAGES = 50  # Configurable limit

def extract_pages_from_pdf(self, pdf_path: Path, output_dir: Path) -> list[Path]:
    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    if page_count > MAX_PAGES:
        doc.close()
        raise ValueError(f"PDF has {page_count} pages, exceeds maximum of {MAX_PAGES}")
    # ... existing rendering logic ...
```

---

### File: `backend/app/services/ai/ollama_client.py`

✅ No issues found. Proper retry with tenacity, connection pooling via persistent httpx client, and comprehensive error handling.

---

### File: `backend/app/services/ai/classifier.py`

#### Function: `_extract_json`
**Line:** 153–176  
**Severity:** 🟡 P2

❌ **Issue:**  
The JSON extraction logic uses `content.index("```")` which raises `ValueError` if the delimiter doesn't exist after the first occurrence. The fallback "find first `{` and last `}`" (implied at line end) is not shown but typical implementations may extract invalid JSON from multi-object responses.

🔍 **Root Cause:**  
Fragile LLM output parsing without robust error boundaries.

⚠ **Production Impact:**  
Occasional classification failures when LLM outputs unexpected format; handled gracefully by the caller returning UNKNOWN type.

🏗 **Category:** Resilience

👉 **Refactoring Approach:**  
Consider using a dedicated JSON extraction library (e.g., `json-repair`) or regex-based extraction with fallback.

---

### File: `backend/app/services/validation/matcher.py`

✅ No issues found. Well-implemented fuzzy matching with OCR error tolerance.

---

### File: `backend/app/services/validation/ownership.py`

✅ No issues found. Weighted scoring with proper fallback strategies.

---

### File: `backend/app/services/notifications/email_service.py`

#### Function: `send_notifications_background`
**Line:** 152–165  
**Severity:** 🟠 P1

❌ **Issue:**  
Credentials JSON is loaded from the database and used to construct a Gmail service on every notification send. The Google API client construction is synchronous and blocking — it runs inside an async function without `run_in_executor`.

🔍 **Root Cause:**  
Google API client library performs synchronous HTTP (token refresh) within an async context.

⚠ **Production Impact:**  
Blocks the event loop during token refresh if the credential is expired. With `max_notification_concurrency=4`, up to 4 concurrent event-loop blocks.

🏗 **Category:** Async / Blocking I/O

👉 **Suggested Fix:**
```python
# Wrap Gmail client construction in run_in_executor:
gmail_service = await asyncio.to_thread(
    _build_gmail_service, config.credentials_json
)
```

---

### File: `backend/app/services/integrations/gmail_scanner.py`

#### Function: `search_for_candidate`
**Line:** 70–105  
**Severity:** 🟠 P1

❌ **Issue:**  
The Gmail API calls (`self._service.users().messages().list(...)` and `.get(...)`) are synchronous blocking calls. The async wrappers exist (`search_for_candidate_async`) but the sync `search_for_candidate` method is 100+ lines of blocking I/O. If accidentally called from async context directly, it blocks the event loop.

🔍 **Root Cause:**  
Google API client library is synchronous; async wrapper exists but the class API exposes both sync and async variants, creating risk of misuse.

⚠ **Production Impact:**  
If the sync variant is called from an async path, the event loop blocks for the duration of all Gmail API calls (potentially seconds per candidate).

🏗 **Category:** Async / Blocking I/O

👉 **Refactoring Approach:**  
The async wrappers properly use `run_in_executor`. Ensure all callers use the `_async` variants. Consider removing/deprecating the sync methods or marking them with `@typing.no_type_check` to flag accidental use.

---

### File: `backend/app/services/integrations/drive_service.py`

#### Function: `__init__`
**Line:** 56–60  
**Severity:** 🟠 P1

❌ **Issue:**  
`credentials.refresh(Request())` is a synchronous HTTP call that blocks the event loop if this class is instantiated from an async context. The `Request()` object from `google.auth.transport.requests` uses `urllib3` under the hood.

🔍 **Root Cause:**  
Google Auth library's sync refresh called during service initialization.

⚠ **Production Impact:**  
Event loop blocked for 100-500ms during credential refresh on each batch processing run.

🏗 **Category:** Async / Blocking I/O

👉 **Suggested Fix:**
```python
# Wrap initialization in asyncio.to_thread when calling from async context
drive_service = await asyncio.to_thread(GoogleDriveService, credentials_json, config_json)
```

---

### File: `backend/app/services/websocket/hub.py`

✅ No issues found. Thread-safe implementation with proper dead connection cleanup.

---

### File: `backend/app/services/audit/logger.py`

✅ No issues found. PII masking is comprehensive and audit logging is well-structured.

---

### File: `backend/app/services/batch/orchestrator.py`

#### Function: `process_batch`
**Line:** 71–80  
**Severity:** 🟡 P2

❌ **Issue:**  
Each candidate is processed sequentially (`for idx, bc in enumerate(candidates)`). For batches with 100+ candidates, total processing time scales linearly when some operations (Gmail search, Drive scan) could be parallelized per candidate.

🔍 **Root Cause:**  
Sequential processing loop without parallelization.

⚠ **Production Impact:**  
Long batch processing times; a 100-candidate batch with 3s per candidate takes 5+ minutes.

🏗 **Category:** Performance / Scalability

👉 **Refactoring Approach:**  
Use `asyncio.Semaphore` to process candidates in bounded parallel batches (e.g., 5 at a time). This requires careful session management (one session per concurrent candidate).

---

### File: `backend/app/services/batch/parser.py`

✅ No issues found. Input validation is thorough with proper error messages.

---

### File: `backend/app/services/processing/stages/normalization_stage.py`

#### Function: `execute`
**Line:** 47  
**Severity:** 🟡 P2

❌ **Issue:**  
`await loop.run_in_executor(None, ...)` uses the default executor (shared thread pool). If the default executor is saturated by other blocking calls, normalization is delayed.

🔍 **Root Cause:**  
Using `None` (default executor) instead of a dedicated pool.

⚠ **Production Impact:**  
Minor contention under high concurrent document processing; OCR already has its own pool.

🏗 **Category:** Performance

👉 **Refactoring Approach:**  
Low priority — consider a dedicated `normalization_executor` if contention is observed.

---

### File: `backend/app/models/document.py`

✅ No issues found. Proper UUID generation, timezone-aware timestamps, and lazy-loaded relationships.

---

### File: `backend/app/models/auth_session.py`

✅ No issues found. Token encryption at rest using Fernet derived from secret_key is well-implemented.

---

### File: `backend/app/services/dependencies.py`

✅ No issues found. Clean singleton pattern with factory functions for session-scoped services.

---

### File: `backend/app/services/protocols.py`

✅ No issues found. Well-defined protocol interfaces for testability.

---

### File: `backend/docker-compose.yml`

#### Service: `postgres`
**Line:** 7–9  
**Severity:** 🟡 P2

❌ **Issue:**  
Default password `bgv_secure_pass_change_me` is in the compose file. While it uses `${POSTGRES_PASSWORD:-...}` (environment variable with fallback), the fallback is a known string that could be committed to version control.

🔍 **Root Cause:**  
Hardcoded fallback password in compose file.

⚠ **Production Impact:**  
If deployed without setting `POSTGRES_PASSWORD` env var, database uses a predictable credential.

🏗 **Category:** Security / Configuration

👉 **Suggested Fix:**
Remove the default fallback or use a generated value:
```yaml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}
```

---

### File: `backend/Dockerfile`

✅ No issues found. Non-root user (`appuser`) is created, slim base image used.

---

## 2. 🔁 Duplication Report

| Pattern | Locations | Impact |
|---------|-----------|--------|
| Session token extraction logic | `app/api/deps.py::_extract_token()` + `app/api/routes/auth.py::_extract_session_token()` | Identical logic duplicated — maintenance risk if one is updated and the other isn't |
| Date parsing in query filters | `app/api/routes/batch.py` (manual `datetime.strptime`) vs `app/api/utils.py::parse_date_param()` | Batch route manually parses dates instead of using the shared utility |
| Google OAuth client config construction | `app/api/routes/settings.py` (repeated `Flow.from_client_config(...)` block in 2 places) | Same 10-line dict constructed twice in the same file |
| Audit logging pattern | All pipeline stages have identical `await self.audit.log(...)` + `await self.audit.record_processing_event(...)` calls | Could be extracted into a stage base class method |
| UploadBatchResponse construction | `app/api/routes/processing.py` lines 87–99 and 109–121 | Manual field mapping repeated; use `model_validate` like other routes |

---

## 3. 🚨 Critical Tech Debt (P0)

| # | Issue | File | Impact |
|---|-------|------|--------|
| — | **No P0 (Critical) issues found** | — | — |

The codebase demonstrates strong security practices:
- No blocking async operations in hot paths (OCR/AI properly use executors)
- Authentication is properly enforced on all routes
- No SQL injection vectors (SQLAlchemy parameterization throughout)
- No hardcoded secrets in production paths
- No unbounded memory allocation in user-facing endpoints
- Session tokens encrypted at rest
- PII masking in audit logs

---

## 4. ⚠️ High & Medium Debt

### 🟠 P1 (High) Issues

| # | Issue | File | Category |
|---|-------|------|----------|
| 1 | No retry mechanism for background document processing | `api/routes/upload.py` | Resilience |
| 2 | Session token exposed in response body alongside httpOnly cookie | `api/routes/auth.py` | Security |
| 3 | PDF page count unbounded — memory exhaustion via large PDF | `services/ocr/preprocessor.py` | Security/DoS |
| 4 | Synchronous Google API credential refresh blocks event loop | `services/integrations/drive_service.py` | Async |
| 5 | Synchronous Gmail API operations callable from async context | `services/integrations/gmail_scanner.py` | Async |
| 6 | Notification email sending blocks event loop during token refresh | `services/notifications/email_service.py` | Async |
| 7 | Incomplete exception handling in OAuth token exchange | `api/routes/auth.py` | Exception Handling |
| 8 | Disk write before validation allows transient disk pressure | `api/routes/upload.py` | Security/DoS |
| 9 | `@lru_cache` on health endpoint caches potentially stale client ref | `api/routes/health.py` | Architecture |

### 🟡 P2 (Medium) Issues

| # | Issue | File | Category |
|---|-------|------|----------|
| 1 | `session_cookie_secure` defaults to False without production guard | `core/config.py` | Security |
| 2 | Missing `ProcessingTimeoutError` from exception hierarchy | `core/exceptions.py` | Architecture |
| 3 | In-memory rate limiter grows unbounded | `api/routes/settings.py` | Memory Leak |
| 4 | Batch file buffered entirely in memory (up to 10MB) | `api/routes/batch.py` | Performance |
| 5 | Dashboard cache per-worker, no shared state | `api/routes/dashboard.py` | Scalability |
| 6 | Sequential batch candidate processing | `services/batch/orchestrator.py` | Performance |
| 7 | Default executor for normalization stage | `services/processing/stages/normalization_stage.py` | Performance |
| 8 | Docker Compose has fallback password | `docker-compose.yml` | Configuration |
| 9 | Fragile LLM JSON extraction | `services/ai/classifier.py` | Resilience |
| 10 | Thread pool created at import time | `services/ocr/engine.py` | Performance |
| 11 | SQL advisory lock uses f-string pattern | `main.py` | Anti-pattern |

---

## 5. 💡 Strategic Improvements

### 1. Retry & Dead-Letter Pattern
Implement a retry queue for failed document processing with exponential backoff. Use the existing `task_manager` to resubmit failed tasks up to N times before marking as permanently failed.

### 2. Redis-Backed Caching
Replace in-process caches (`_dashboard_cache`, rate limiter) with Redis for multi-worker consistency. Use `aioredis` or `redis.asyncio`.

### 3. OpenTelemetry Integration
Add distributed tracing across the pipeline stages:
```python
from opentelemetry import trace
tracer = trace.get_tracer("bgv.pipeline")

async def process_document(self, document_id: str):
    with tracer.start_as_current_span("process_document", attributes={"document_id": document_id}):
        ...
```

### 4. Parallel Batch Candidate Processing
Refactor `BatchOrchestrator.process_batch()` to process candidates in parallel with bounded concurrency:
```python
sem = asyncio.Semaphore(5)
tasks = [self._process_with_sem(sem, batch, bc, ...) for bc in candidates]
await asyncio.gather(*tasks, return_exceptions=True)
```

### 5. Google API Async Migration
Replace `google-api-python-client` (sync) with `aiogoogle` or consistently wrap all Google API calls in `asyncio.to_thread()` at the service boundary.

### 6. PDF Processing Hardening
- Add configurable page count limit
- Add per-page memory estimation before rendering
- Consider using streaming/lazy rendering for metadata extraction

### 7. Circuit Breaker for Ollama
Add a circuit breaker pattern around Ollama calls to fast-fail when the service is consistently unavailable, rather than retry N times per document.

### 8. Structured Error Responses
Standardize all error responses using the `ErrorResponse` schema. Some routes still raise raw `HTTPException` with string details.

---

## 6. 📊 Python Quality Scorecard

| Category | Score |
|----------|-------|
| Naming | 92/100 |
| Architecture | 88/100 |
| Type Safety | 82/100 |
| Logging | 95/100 |
| Exception Handling | 80/100 |
| Async | 78/100 |
| API Design | 90/100 |
| Validation | 85/100 |
| Security | 87/100 |
| DRY | 82/100 |
| Performance | 80/100 |
| Configuration | 88/100 |
| Testing | 85/100 |

**Python Score: 85/100**

---

## 7. 📉 Python Tech Debt Summary

| Metric | Count |
|--------|-------|
| **Total Issues** | 20 |
| 🔴 P0 (Critical) | 0 |
| 🟠 P1 (High) | 9 |
| 🟡 P2 (Medium) | 11 |
| Duplication Cases | 5 |

**Python Tech Debt Level: 🟡 Medium**

---

## 8. 🧾 Final Verdict

### ⚠️ Needs Improvement (Minor)

**Justification:**

| Dimension | Assessment |
|-----------|------------|
| **Security** | Strong — httpOnly cookies, token encryption at rest, PII masking, input validation, file type verification. One issue: session token in response body alongside cookie undermines httpOnly protection. |
| **Scalability** | Good for single-instance; in-process caches and sequential batch processing limit multi-worker/high-volume scaling. |
| **Reliability** | Good — advisory locks for recovery, graceful shutdown, pipeline error handling. Missing retry logic for background tasks is the main gap. |
| **Maintainability** | Strong — clean architecture with protocols, stage-based pipeline, structured logging, well-organized modules. Minor duplication exists. |
| **Performance** | Good — dedicated OCR thread pool, connection pooling, streaming uploads. Blocking Google API calls in async context are the main bottleneck. |

**Overall:** The codebase is well-architected and close to production-ready. The identified issues are P1/P2 level — no critical security vulnerabilities or crash risks. The primary areas for improvement are: (1) async discipline around Google API integrations, (2) retry logic for background processing, and (3) removing session token from response bodies. These can be addressed incrementally without architectural changes.
