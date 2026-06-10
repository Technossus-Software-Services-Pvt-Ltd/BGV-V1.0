# 🐍 Python Tech Debt Audit Report — v13

**Date:** 2026-06-08  
**Auditor:** Principal Python Architect / Staff Security Engineer  
**Scope:** Full backend codebase (`backend/app/`)  
**Stack:** Python 3.11+ | FastAPI | SQLAlchemy 2.x (async) | Pydantic v2 | PaddleOCR | Ollama | OpenAI | Google APIs

---

## 1. 📁 File-Level Tech Debt

---

### File: `backend/app/main.py`

#### Function: `_recover_stuck_documents`
**Line:** 63–76  
**Severity:** 🟠 P1

❌ **Issue:**  
Advisory lock SQL uses f-string interpolation with integer constants. While safe today (constants are hardcoded ints), the pattern encourages unsafe SQL construction elsewhere.

🔍 **Root Cause:**  
Using `text(f"SELECT pg_advisory_lock({ADVISORY_LOCK_DOCUMENT_RECOVERY})")` instead of parameterized query.

⚠ **Production Impact:**  
SQL injection pattern proliferation risk. If someone copies this pattern with user input, it becomes a critical vulnerability.

🏗 **Category:** Security / Anti-pattern

👉 **Suggested Fix:**
```python
await db.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_DOCUMENT_RECOVERY})
```

---

#### Function: `catch_unhandled_exceptions` (middleware)
**Line:** 173–189  
**Severity:** 🟡 P2

❌ **Issue:**  
The middleware catches exceptions raised by `call_next`, but in Starlette/FastAPI, `call_next` wraps the response in a `StreamingResponse`. Exceptions that occur during response streaming (after headers are sent) will NOT be caught by this middleware — they'll result in incomplete responses.

🔍 **Root Cause:**  
Starlette's ASGI streaming model means the body generator runs after `call_next` returns. Only exceptions raised before streaming begins are caught.

⚠ **Production Impact:**  
Some unhandled exceptions during response body generation will leak as connection resets rather than structured 500 JSON.

🏗 **Category:** Architecture

👉 **Refactoring Approach:**  
This is an inherent ASGI limitation. Document this behavior and add request-level exception middleware using `@app.middleware("http")` wisely — ensure streaming endpoints handle their own errors.

---

### File: `backend/app/core/config.py`

#### Class: `Settings`
**Line:** 98–100  
**Severity:** 🟠 P1

❌ **Issue:**  
Development fallback database URL contains hardcoded credentials: `postgresql+asyncpg://bgv_user:bgv_dev_pass@localhost:5432/bgv_db`. While tagged as development-only, this can leak into logs, tracebacks, or `.env` template copies.

🔍 **Root Cause:**  
Hardcoded dev credentials in the settings validator fallback logic.

⚠ **Production Impact:**  
If `environment` variable is accidentally unset or misconfigured in staging, these credentials become active. Credential exposure in stack traces.

🏗 **Category:** Security / Configuration

👉 **Suggested Fix:**
```python
if not self.database_url:
    if self.environment == "development":
        import warnings
        warnings.warn("DATABASE_URL not set; using local dev default", stacklevel=2)
        self.database_url = "postgresql+asyncpg://bgv_user:bgv_dev_pass@localhost:5432/bgv_db"
    else:
        raise ValueError("DATABASE_URL must be set in production")
```
Better: Move dev defaults to a `.env.example` file and never embed credentials in source.

---

#### Property: `upload_path`
**Line:** 137–139  
**Severity:** 🟡 P2

❌ **Issue:**  
`Path.mkdir(parents=True, exist_ok=True)` is called every time the property is accessed — on every upload request. This is I/O on every access of a computed property.

🔍 **Root Cause:**  
Side-effectful property without caching. Properties should be idempotent getters.

⚠ **Production Impact:**  
Unnecessary filesystem syscalls under high load. Minor but violates principle of least surprise.

🏗 **Category:** Performance / Anti-pattern

👉 **Suggested Fix:**
```python
@property
def upload_path(self) -> Path:
    return Path(self.upload_dir)

# Call mkdir once at startup in lifespan()
```

---

### File: `backend/app/core/security.py`

✅ No critical issues found. File-content MIME validation, filename sanitization, and size checks are well-implemented.

---

### File: `backend/app/core/logging.py`

**Line:** 28–34  
**Severity:** 🟡 P2

❌ **Issue:**  
`_log_level_to_int` uses string comparison with a hardcoded mapping but the config default is `"Info"` (title-case). The `.upper()` call handles this, but there's no validation that the config value is a valid log level.

🔍 **Root Cause:**  
No field_validator on `log_level` in Settings to constrain it to valid choices.

⚠ **Production Impact:**  
Typo in config silently defaults to INFO (20). No error or warning for misconfigured log level.

🏗 **Category:** Configuration / Validation

👉 **Suggested Fix:**
Add to `Settings`:
```python
@field_validator("log_level")
@classmethod
def validate_log_level(cls, v: str) -> str:
    valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if v.upper() not in valid:
        raise ValueError(f"log_level must be one of {valid}")
    return v
```

---

### File: `backend/app/core/exceptions.py`

✅ No issues found. Well-structured exception hierarchy with correct HTTP status mapping.

---

### File: `backend/app/db/session.py`

**Line:** 4–7  
**Severity:** 🟡 P2

❌ **Issue:**  
`pool_size=5` and `max_overflow=10` are hardcoded. In production with multiple workers (uvicorn workers × 5 connections = pool exhaustion under load). These should be configurable.

🔍 **Root Cause:**  
Connection pool sizing is not configurable via environment/settings.

⚠ **Production Impact:**  
Under concurrent load with multiple workers, the database connection pool can become exhausted, leading to request queuing/timeouts.

🏗 **Category:** Scalability / Configuration

👉 **Suggested Fix:**
Add to `Settings`:
```python
db_pool_size: int = 5
db_max_overflow: int = 10
```
Use in session.py:
```python
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)
```

---

### File: `backend/app/db/base.py`

✅ No issues found. Good naming convention configuration.

---

### File: `backend/app/api/deps.py`

✅ No issues found. Session validation with single joined query is efficient. Token extraction priority (cookie → header → fallback) is correct.

---

### File: `backend/app/api/routes/upload.py`

#### Function: `upload_documents`
**Line:** 109–113  
**Severity:** 🟠 P1

❌ **Issue:**  
Early MIME validation writes partial data to disk before detecting disallowed content type. When `detected_mime not in ALLOWED_MIME_TYPES`, the code breaks out of the write loop but has already written the first chunk, then relies on cleanup. However, the actual logic flow is flawed: after writing one chunk and breaking, `mime_validated` remains `False`, but the subsequent `validate_file_content()` call at line 125 re-validates the header bytes anyway.

🔍 **Root Cause:**  
Confusing control flow with double-validation (early check + post-write check). The early check writes data before rejecting, creating temporary invalid files.

⚠ **Production Impact:**  
Disk space temporarily consumed by invalid files. Race condition window where invalid files exist on disk.

🏗 **Category:** Architecture / Security

👉 **Suggested Fix:**
```python
# Read first chunk, validate MIME before writing anything
first_chunk = await file.read(1024 * 1024)
if not first_chunk:
    raise HTTPException(status_code=400, detail="Empty file uploaded")

header_bytes = first_chunk[:2048]
detected_mime = _detect_mime_from_magic_bytes(header_bytes)
if detected_mime not in ALLOWED_MIME_TYPES:
    raise HTTPException(status_code=400, detail=f"File content type '{detected_mime}' not allowed")

# Now write to disk
async with aiofiles.open(file_path, "wb") as f:
    await f.write(first_chunk)
    file_size = len(first_chunk)
    while chunk := await file.read(1024 * 1024):
        file_size += len(chunk)
        if file_size > settings.max_upload_size_bytes:
            break
        await f.write(chunk)
```

---

#### Function: `upload_documents`
**Line:** 42–43  
**Severity:** 🟡 P2

❌ **Issue:**  
`candidate_name` is accepted as a Form field with `min_length=1, max_length=255` but NO sanitization for HTML/script content. It's stored directly in the database and returned in API responses.

🔍 **Root Cause:**  
Missing input sanitization for display-bound string fields.

⚠ **Production Impact:**  
Stored XSS if the frontend renders this field without escaping (defense-in-depth gap).

🏗 **Category:** Security / Validation

👉 **Suggested Fix:**  
Add HTML entity stripping/sanitization in the schema or at the API boundary:
```python
from html import escape
candidate_name = escape(candidate_name.strip())
```

---

### File: `backend/app/api/routes/auth.py`

#### Function: `google_auth_callback`
**Line:** 164–170  
**Severity:** 🟡 P2

❌ **Issue:**  
OAuth state is validated but the `redirect_uri` stored in the OAuth state is used directly for the token exchange without validating it against an allowlist. A compromised database state record could redirect tokens to an attacker-controlled URI.

🔍 **Root Cause:**  
Trust in DB-stored redirect_uri without re-validation against allowed origins.

⚠ **Production Impact:**  
If an attacker can inject a state record into the DB (e.g., via SQL injection elsewhere), they could redirect OAuth tokens to their endpoint. Defense-in-depth gap.

🏗 **Category:** Security

👉 **Suggested Fix:**
```python
# Validate redirect_uri from state against allowed origins
allowed_origins = settings.cors_origins_list
parsed = urlparse(redirect_uri)
origin = f"{parsed.scheme}://{parsed.netloc}"
if origin not in allowed_origins:
    raise HTTPException(status_code=400, detail="Invalid redirect URI")
```

---

#### Function: `_resolve_redirect_uri`
**Line:** 88–100  
**Severity:** 🟠 P1

❌ **Issue:**  
The `origin` header from the request is used to dynamically construct the redirect URI. An attacker can forge the `Origin` header to redirect OAuth callbacks to their domain.

🔍 **Root Cause:**  
Trusting client-supplied `Origin`/`Referer` headers for OAuth redirect construction without validating against an allowlist.

⚠ **Production Impact:**  
OAuth token theft via redirect manipulation. Attacker sends `Origin: https://evil.com`, gets redirect_uri set to `https://evil.com/auth/callback`.

🏗 **Category:** Security (OAuth)

👉 **Suggested Fix:**
```python
def _resolve_redirect_uri(request: Optional[Request], redirect_uri: Optional[str]) -> str:
    if redirect_uri:
        # Validate against allowlist
        parsed = urlparse(redirect_uri)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in settings.cors_origins_list:
            raise HTTPException(status_code=400, detail="Invalid redirect URI")
        return redirect_uri

    # Default to configured redirect URI — never trust Origin header for OAuth
    return settings.google_redirect_uri
```

---

### File: `backend/app/api/routes/documents.py`

#### Function: `list_documents`
**Line:** 58–66  
**Severity:** 🟡 P2

❌ **Issue:**  
The `doc_ids` list is built and used in a subsequent `.in_()` query without batching. For large document sets (100+ docs), this generates a massive SQL `IN` clause which degrades database performance.

🔍 **Root Cause:**  
Unbounded `IN` clause for validation result lookup.

⚠ **Production Impact:**  
Slow queries when document counts grow. PostgreSQL query planner performance degrades with large IN lists.

🏗 **Category:** Performance / Scalability

👉 **Suggested Fix:**  
Use a joined/subquery approach or batch the IN clause:
```python
# Use a join instead of IN clause
query = (
    select(Document, ValidationResult)
    .outerjoin(ValidationResult, ValidationResult.document_id == Document.id)
    .order_by(Document.created_at.desc())
    ...
)
```

---

### File: `backend/app/api/routes/batch.py`

#### Function: `upload_batch_file`
**Line:** 63–71  
**Severity:** 🟡 P2

❌ **Issue:**  
File content is accumulated in memory (`chunks.append(chunk)` then `b"".join(chunks)`). For a 10MB file, this allocates ~20MB (chunks list + joined bytes). Should use streaming to disk.

🔍 **Root Cause:**  
Buffering entire file in memory before writing to disk.

⚠ **Production Impact:**  
Under concurrent batch uploads, memory spikes of 20MB × concurrent_uploads. With 10 simultaneous uploads = 200MB of memory for file buffering alone.

🏗 **Category:** Performance / Memory

👉 **Suggested Fix:**
```python
# Stream directly to disk with size enforcement
file_path = file_dir / stored_name
total_size = 0
async with aiofiles.open(file_path, "wb") as f:
    while chunk := await file.read(64 * 1024):
        total_size += len(chunk)
        if total_size > max_size:
            # Cleanup partial file
            Path(file_path).unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Import file must be under 10MB")
        await f.write(chunk)
```

---

### File: `backend/app/api/routes/dashboard.py`

#### Function: `get_dashboard_stats`
**Line:** 35–130  
**Severity:** 🟡 P2

❌ **Issue:**  
The dashboard executes 7 separate database queries sequentially. These queries are independent and could be executed concurrently using `asyncio.gather`, reducing response latency by ~5-7x.

🔍 **Root Cause:**  
Sequential execution of independent queries.

⚠ **Production Impact:**  
Dashboard response time is the SUM of all query latencies instead of the MAX. With 7 queries at 20ms each = 140ms vs potential 25ms.

🏗 **Category:** Performance

👉 **Refactoring Approach:**  
Note: `AsyncSession` is NOT safe for concurrent use from a single session. Each concurrent query needs its own session, or use a single composite SQL query. The correct approach here is to combine into fewer queries or use raw SQL with CTEs:
```python
# Use a single CTE-based query to fetch all stats in one round-trip
stats_query = text("""
    WITH doc_stats AS (...),
         batch_stats AS (...),
         ...
    SELECT * FROM doc_stats, batch_stats, ...
""")
```

---

### File: `backend/app/api/routes/settings.py`

#### Function: `_callback_attempts` (rate limiter)
**Line:** 47–55  
**Severity:** 🟠 P1

❌ **Issue:**  
In-memory rate limiting (`_callback_attempts` dict) does NOT work in multi-worker deployments. Each uvicorn worker has its own dict, so the effective rate limit is `workers × _CALLBACK_RATE_LIMIT` per IP. Also, the dict is never pruned for expired IPs — it's a **memory leak**.

🔍 **Root Cause:**  
Process-local in-memory state for rate limiting without expiry cleanup for dead entries.

⚠ **Production Impact:**  
- Rate limiting is ineffective in multi-worker deployments.
- Memory leak: new unique IPs accumulate in `_callback_attempts` indefinitely (only timestamps are pruned, not empty IP entries).

🏗 **Category:** Security / Memory Leak

👉 **Suggested Fix:**
```python
# Use TTL-based dict with max size, or Redis for distributed rate limiting
from collections import OrderedDict

class RateLimiter:
    def __init__(self, max_entries: int = 10000, limit: int = 5, window: int = 60):
        self._entries: OrderedDict[str, list[float]] = OrderedDict()
        self._max_entries = max_entries
        self._limit = limit
        self._window = window

    def is_limited(self, key: str) -> bool:
        now = time.monotonic()
        # Evict oldest entries if over capacity
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        attempts = self._entries.get(key, [])
        attempts = [t for t in attempts if now - t < self._window]
        if len(attempts) >= self._limit:
            self._entries[key] = attempts
            return True
        attempts.append(now)
        self._entries[key] = attempts
        return False
```

---

### File: `backend/app/api/routes/ws.py`

✅ No critical issues found. WebSocket authentication with single-use tickets and timeout handling is well-implemented.

---

### File: `backend/app/api/routes/health.py`

**Line:** 11–13  
**Severity:** 🟡 P2

❌ **Issue:**  
`@lru_cache(maxsize=1)` on `_get_ollama_client()` returns the same client instance forever. If the OllamaClient's underlying httpx connection pool becomes stale or broken, health checks will always fail until process restart.

🔍 **Root Cause:**  
Caching a mutable network client without invalidation.

⚠ **Production Impact:**  
Stale health check results after network disruptions.

🏗 **Category:** Architecture

👉 **Suggested Fix:**  
The client is already a singleton via `dependencies.py`. Remove the `@lru_cache` and use the dependency directly:
```python
@router.get("/health")
async def health_check():
    client = get_ai_classifier().client
    ...
```

---

### File: `backend/app/api/routes/review_queue.py`

✅ No critical issues found. Proper pagination, search, and status filtering.

---

### File: `backend/app/services/task_manager.py`

✅ No critical issues found. Well-designed with semaphore concurrency control, graceful shutdown, and task tracking.

---

### File: `backend/app/services/dependencies.py`

**Line:** 27–33  
**Severity:** 🟡 P2

❌ **Issue:**  
Module-level instantiation of `PaddleOCREngine()` triggers model loading at import time. If the PaddleOCR model files are missing or corrupt, the entire application fails to start with an unhelpful import error.

🔍 **Root Cause:**  
Eager initialization of heavy ML dependencies at module level.

⚠ **Production Impact:**  
Application startup failure if OCR model files are unavailable. No graceful degradation.

🏗 **Category:** Architecture / Resilience

👉 **Suggested Fix:**  
Use lazy initialization:
```python
_ocr_engine: Optional[PaddleOCREngine] = None

def get_ocr_engine() -> PaddleOCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCREngine()
    return _ocr_engine
```

---

### File: `backend/app/services/ai/classifier.py`

**Line:** 84  
**Severity:** 🟡 P2

❌ **Issue:**  
OCR text is truncated to 3000 characters with a hard slice: `ocr_text[:3000]`. This can cut text mid-word or mid-sentence, potentially splitting critical identifying information (like a name across the boundary).

🔍 **Root Cause:**  
Naive character-based truncation without respecting word/sentence boundaries.

⚠ **Production Impact:**  
AI classification may fail on documents where key identifiers fall near the 3000-char boundary.

🏗 **Category:** AI/ML Integration

👉 **Suggested Fix:**
```python
def _smart_truncate(text: str, max_chars: int = 3000) -> str:
    if len(text) <= max_chars:
        return text
    # Find last space before max_chars
    cut_point = text.rfind(" ", 0, max_chars)
    return text[:cut_point] if cut_point > max_chars * 0.8 else text[:max_chars]
```

---

### File: `backend/app/services/ai/ollama_client.py`

✅ No critical issues found. Good retry logic with tenacity, connection pooling via persistent httpx client, and proper error handling.

---

### File: `backend/app/services/ai/openai_validator.py`

✅ No critical issues found. Proper timeout, error handling, and cost tracking.

---

### File: `backend/app/services/ocr/engine.py`

#### Function: `process` / `process_from_path`
**Line:** 127–150  
**Severity:** 🟡 P2

❌ **Issue:**  
The synchronous `process()` and `process_from_path()` methods are public API. If accidentally called from an async context without going through `process_async()`, they block the event loop.

🔍 **Root Cause:**  
Blocking methods are publicly exposed alongside async variants without any protection or naming convention enforcement.

⚠ **Production Impact:**  
If a developer calls `ocr_engine.process()` from an async handler, it blocks the event loop for the duration of OCR (potentially 5-30 seconds), stalling all concurrent requests.

🏗 **Category:** Async / Architecture

👉 **Suggested Fix:**  
Prefix sync methods with underscore to signal they're internal:
```python
def _process_sync(self, image_array: np.ndarray) -> OCREngineResult:
    ...

async def process(self, image_array: np.ndarray) -> OCREngineResult:
    """Primary API — always non-blocking."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_ocr_executor, self._process_sync, image_array)
```

---

### File: `backend/app/services/processing/pipeline.py`

✅ No critical issues found. Clean stage-based architecture with proper context passing.

---

### File: `backend/app/services/processing/normalizer.py`

**Line:** 38–42  
**Severity:** 🟡 P2

❌ **Issue:**  
`extract_pages` and `count_pdf_pages` use PyMuPDF synchronously. When called from the pipeline (which runs in background asyncio tasks), these block the event loop since the normalization stage doesn't use `run_in_executor`.

🔍 **Root Cause:**  
Synchronous I/O-bound operations (PDF parsing) called from async context without executor.

⚠ **Production Impact:**  
Event loop blocked during PDF page extraction. For a 50-page PDF at 300 DPI, this could block for 2-5 seconds.

🏗 **Category:** Async / Performance

👉 **Suggested Fix:**  
Wrap in `asyncio.to_thread()` in the normalization stage, or provide async variants.

---

### File: `backend/app/services/processing/splitter.py`

✅ No issues found. Clean grouping logic.

---

### File: `backend/app/services/processing/stages/context.py`

✅ No issues found. Clean dataclass context.

---

### File: `backend/app/services/processing/stages/ocr_stage.py`

✅ No issues found. Properly uses async OCR engine.

---

### File: `backend/app/services/processing/stages/validation_stage.py`

**Line:** 1 & 20  
**Severity:** 🟡 P2

❌ **Issue:**  
Duplicate import: `from app.services.ai.openai_validator import OpenAIOwnershipResult` appears twice (line 1 and line 20 relative to shown content).

🔍 **Root Cause:**  
Copy-paste error during development.

⚠ **Production Impact:**  
No runtime impact but indicates code review gaps.

🏗 **Category:** Maintainability

👉 **Suggested Fix:**  
Remove the duplicate import.

---

### File: `backend/app/services/batch/orchestrator.py`

✅ No critical issues found. Well-delegated orchestrator pattern with proper error handling and cleanup.

---

### File: `backend/app/services/batch/ingest_service.py`

**Line:** 65–70  
**Severity:** 🟡 P2

❌ **Issue:**  
Downloaded file bytes from Gmail are fully loaded into memory before size check. A malicious email with a 500MB attachment would consume 500MB of memory before being rejected.

🔍 **Root Cause:**  
`gmail_scanner.download_attachment` returns full file bytes. No streaming download with early termination.

⚠ **Production Impact:**  
Memory exhaustion from large malicious attachments. OOM kill risk under batch processing.

🏗 **Category:** Performance / Memory / Security

👉 **Suggested Fix:**  
Implement streaming download with size limit enforcement:
```python
file_bytes = await loop.run_in_executor(
    _io_executor, gmail_scanner.download_attachment, att.message_id, att.attachment_id
)
# This is a limitation of the Gmail API which returns full content
# Mitigate by checking size metadata first
if att.size_bytes > settings.max_upload_size_bytes:
    failed_count += 1
    continue
```

---

### File: `backend/app/services/batch/discovery_service.py`

**Line:** 24  
**Severity:** 🟡 P2

❌ **Issue:**  
`_io_executor` is duplicated between `discovery_service.py` and `ingest_service.py`. Both create separate `ThreadPoolExecutor` instances for the same purpose (Google API I/O). This wastes threads and makes the concurrency model confusing.

🔍 **Root Cause:**  
Code duplication of thread pool creation.

⚠ **Production Impact:**  
Double the thread resources consumed (2 pools × google_io_pool_size threads).

🏗 **Category:** DRY / Architecture

👉 **Suggested Fix:**  
Create a shared executor in a common module:
```python
# app/services/integrations/executor.py
from concurrent.futures import ThreadPoolExecutor
from app.core.config import settings

google_io_executor = ThreadPoolExecutor(
    max_workers=settings.google_io_pool_size,
    thread_name_prefix="google-io"
)
```

---

### File: `backend/app/services/batch/status_service.py`

✅ No issues found. Clean separation of concerns.

---

### File: `backend/app/services/websocket/hub.py`

✅ No critical issues found. Proper lock-based concurrency and dead connection cleanup.

---

### File: `backend/app/services/validation/ownership.py`

✅ No critical issues found. Well-structured weighted scoring with fallback logic.

---

### File: `backend/app/services/audit/logger.py`

✅ No issues found. Good PII masking implementation.

---

### File: `backend/app/services/notifications/email_service.py`

✅ No critical issues found. HTML escaping applied to candidate names. Good defensive coding.

---

### File: `backend/app/services/integrations/gmail_scanner.py`

**Line:** 62  
**Severity:** 🟡 P2

❌ **Issue:**  
The `GmailScanner.__init__` uses synchronous Google API client building (`build("gmail", "v1", ...)`). This performs network I/O (discovery document fetch) synchronously. It's wrapped in `asyncio.to_thread` in the caller, which is correct, but the class itself doesn't document this requirement.

🔍 **Root Cause:**  
Synchronous constructor performing network I/O.

⚠ **Production Impact:**  
If called without `to_thread`, blocks event loop. The dependency on external calling convention is fragile.

🏗 **Category:** Architecture / Documentation

👉 **Suggested Fix:**  
Add `cache_discovery=False` (already present — good) and document in docstring that this must be called from a thread.

---

### File: `backend/app/services/batch/parser.py`

✅ No issues found. Good column aliasing, validation, and error reporting.

---

### File: `backend/app/models/document.py`

✅ No issues found. Proper UUID generation, timezone-aware timestamps, and relationship definitions.

---

### File: `backend/app/models/candidate.py`

✅ No issues found.

---

### File: `backend/app/models/auth_session.py`

✅ No issues found. Good encryption of stored tokens with Fernet.

---

### File: `backend/app/models/enums.py`

✅ No issues found. Clean string enum definitions.

---

### File: `backend/app/schemas/candidate.py`

✅ No issues found. Proper Pydantic v2 usage with `from_attributes`.

---

### File: `backend/app/services/ocr/preprocessor.py`

✅ No issues found. Good image normalization pipeline.

---

### File: `backend/app/services/ocr/confidence.py`

✅ No issues found. Clean threshold-based evaluation.

---

### File: `backend/app/services/protocols.py`

✅ No issues found. Good use of `@runtime_checkable` protocols for DI contracts.

---

## 2. 🔁 Duplication Report

| Duplicate Pattern | Locations | Severity |
|---|---|---|
| ThreadPoolExecutor for Google I/O | `batch/discovery_service.py`, `batch/ingest_service.py` | 🟡 P2 |
| Advisory lock acquire/release pattern | `main.py` (2 occurrences: documents + batches) | 🟡 P2 |
| File streaming + size validation | `api/routes/upload.py`, `api/routes/batch.py` | 🟡 P2 |
| `get_db` session pattern with rollback | `db/session.py` (used everywhere, which is correct DI) | ✅ OK |
| Validation import `OpenAIOwnershipResult` | `stages/validation_stage.py` (duplicated import) | 🟡 P2 |
| Batch code generation logic | Only in `batch.py` route — not duplicated | ✅ OK |

**Total Duplication Cases: 4**

---

## 3. 🚨 Critical Tech Debt (P0)

| # | Issue | File | Impact |
|---|---|---|---|
| — | *None identified* | — | — |

**No P0 critical issues found.** The codebase does not exhibit blocking async event loop operations in hot paths (OCR uses `run_in_executor`), authentication is properly implemented with httpOnly cookies and session validation, and there are no SQL injection vulnerabilities or data leak vectors.

---

## 4. ⚠️ High & Medium Debt

### 🟠 P1 (High) Issues

| # | Issue | File | Category |
|---|---|---|---|
| 1 | OAuth redirect URI constructed from untrusted Origin header | `api/routes/auth.py:88-100` | Security |
| 2 | Upload writes file before MIME validation | `api/routes/upload.py:109-113` | Security/Architecture |
| 3 | In-memory rate limiter doesn't work multi-worker + memory leak | `api/routes/settings.py:47-55` | Security/Memory |
| 4 | Hardcoded dev DB credentials in source | `core/config.py:98-100` | Security/Configuration |
| 5 | SQL advisory lock uses f-string interpolation | `main.py:63-76` | Security (pattern) |

### 🟡 P2 (Medium) Issues

| # | Issue | File | Category |
|---|---|---|---|
| 1 | DB pool size not configurable | `db/session.py:4-7` | Scalability |
| 2 | `upload_path` property has side effects | `core/config.py:137-139` | Anti-pattern |
| 3 | No log_level validation | `core/logging.py:28-34` | Configuration |
| 4 | Candidate name not sanitized for XSS | `api/routes/upload.py:42-43` | Security |
| 5 | Unbounded IN clause for validation lookup | `api/routes/documents.py:58-66` | Performance |
| 6 | Batch file buffered fully in memory | `api/routes/batch.py:63-71` | Memory |
| 7 | Sequential dashboard queries | `api/routes/dashboard.py:35-130` | Performance |
| 8 | LRU-cached network client in health | `api/routes/health.py:11-13` | Architecture |
| 9 | Eager OCR engine initialization | `services/dependencies.py:27-33` | Resilience |
| 10 | Naive text truncation for AI | `services/ai/classifier.py:84` | AI/ML |
| 11 | Sync OCR methods publicly exposed | `services/ocr/engine.py:127-150` | Async |
| 12 | Sync PDF operations in async context | `services/processing/normalizer.py:38-42` | Async |
| 13 | Duplicate import | `stages/validation_stage.py:1,20` | Maintainability |
| 14 | Gmail full download before size check | `services/batch/ingest_service.py:65-70` | Memory |
| 15 | Duplicate ThreadPoolExecutor | `batch/discovery_service.py + ingest_service.py` | DRY |

---

## 5. 💡 Strategic Improvements

### 5.1 Architecture Redesign

1. **Extract file upload service**: Consolidate file streaming, MIME validation, and disk write logic into a reusable `FileStorageService` to eliminate duplication between upload and batch routes.

2. **Lazy service initialization**: Move all heavyweight service instantiation (OCR engine, AI classifier) to first-use lazy loading with proper health degradation.

### 5.2 Async Optimization

1. **PDF normalization**: Wrap all PyMuPDF calls in `asyncio.to_thread()` in the normalization stage.
2. **Dashboard queries**: Combine into a single CTE-based SQL query to reduce from 7 round-trips to 1.

### 5.3 Caching Strategy

1. **Dashboard cache** (already implemented with 30s TTL — good).
2. **Add OCR model warm-up**: Pre-load PaddleOCR model on startup to avoid first-request latency spike.
3. **Consider Redis** for distributed rate limiting and cross-worker session cache.

### 5.4 Observability Improvements

1. **Add correlation_id to structlog contextvars** at request start for automatic propagation.
2. **Add request duration metrics** middleware for monitoring.
3. **OpenTelemetry integration**: Add trace spans around OCR, AI classification, and DB queries for latency analysis.

```python
# Example: middleware for request tracing
from opentelemetry import trace
tracer = trace.get_tracer("bgv.api")

@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    with tracer.start_as_current_span(f"{request.method} {request.url.path}"):
        return await call_next(request)
```

### 5.5 Queue Processing

1. **Consider Celery/ARQ for batch processing**: The current `asyncio.create_task` approach works for single-worker deployments but doesn't survive process restarts. Persistent job queues (ARQ with Redis) would provide at-least-once delivery guarantees.

### 5.6 AI Inference Optimization

1. **Request batching for Ollama**: When processing multi-page documents, batch classification requests instead of sequential per-page calls.
2. **Model response caching**: Cache AI classification results for identical OCR text hashes to avoid redundant LLM calls.

### 5.7 Resilience Patterns

1. **Circuit breaker for Ollama**: After N consecutive failures, stop sending requests for a cooldown period.
2. **Dead letter queue for failed documents**: Instead of marking as FAILED permanently, queue for manual retry.

---

## 6. 📊 Python Quality Scorecard

| Dimension | Score | Notes |
|---|---|---|
| **Naming** | 90/100 | Consistent, descriptive names. Minor: `_callback_attempts` could be more descriptive. |
| **Architecture** | 88/100 | Clean stage-based pipeline, proper DI. Deducted for file storage duplication and lazy-init gap. |
| **Type Safety** | 85/100 | Good type hints throughout. Missing on some internal helpers. Pydantic v2 used correctly. |
| **Logging** | 92/100 | Excellent structured logging with structlog. PII masking. Correlation IDs. |
| **Exception Handling** | 90/100 | Domain exception hierarchy with global handler. Good error isolation in background tasks. |
| **Async** | 82/100 | OCR properly offloaded. Deducted for sync normalizer and exposed sync OCR methods. |
| **API Design** | 90/100 | RESTful, versioned, proper status codes, pagination, filtering. |
| **Validation** | 85/100 | Pydantic schemas, file validation, MIME checking. Missing XSS sanitization and some input constraints. |
| **Security** | 80/100 | Good auth (httpOnly cookies, encrypted tokens). Deducted for OAuth redirect trust, in-memory rate limiter, hardcoded dev creds. |
| **DRY** | 85/100 | Good abstraction overall. Minor duplication in thread pools and file streaming. |
| **Performance** | 82/100 | OCR concurrency control good. Dashboard queries sequential. Memory buffering concerns. |
| **Configuration** | 85/100 | Pydantic settings with validation. Missing pool size config and log level validation. |
| **Testing** | 75/100 | Test files exist but coverage appears limited based on file structure. |

### **Python Score: 85/100**

---

## 7. 📉 Python Tech Debt Summary

| Metric | Count |
|---|---|
| **Total Issues** | 20 |
| 🔴 **P0 (Critical)** | 0 |
| 🟠 **P1 (High)** | 5 |
| 🟡 **P2 (Medium)** | 15 |
| **Duplication Cases** | 4 |

### Python Tech Debt Level: 🟡 Medium

The codebase has solid architectural foundations with a well-designed stage-based processing pipeline, proper async patterns for the heaviest operations (OCR), and good security practices (httpOnly cookies, PII masking, encrypted token storage). The debt is concentrated in:
- OAuth security gaps (redirect URI trust)
- Memory management in file handling
- Some async gaps in PDF operations
- Configuration rigidity

---

## 8. 🧾 Final Verdict

### ⚠️ Needs Improvement

**Justification:**

| Dimension | Assessment |
|---|---|
| **Security** | ⚠️ OAuth redirect URI vulnerability and in-memory rate limiter bypass in multi-worker mode need immediate fixes before production hardening. Token storage encryption is good. |
| **Scalability** | ⚠️ Single-worker assumptions (in-memory rate limiter, in-process task queue). DB pool not configurable. Dashboard query latency grows with data. |
| **Reliability** | ✅ Good. Stuck document/batch recovery on startup. Graceful shutdown. Advisory locks for concurrency. Background task management. |
| **Maintainability** | ✅ Good. Clean architecture, proper separation of concerns, protocol-based DI, domain exceptions, structured logging. |
| **Performance** | ⚠️ Some blocking operations in async paths (PDF normalization). Memory buffering for file uploads. Sequential dashboard queries. |

**Priority Fix Order:**
1. 🟠 Fix OAuth redirect URI validation (security)
2. 🟠 Fix rate limiter for multi-worker + memory leak (security)
3. 🟠 Fix file upload MIME validation order (security)
4. 🟡 Make DB pool configurable (scalability)
5. 🟡 Wrap PDF operations in `asyncio.to_thread` (async correctness)
