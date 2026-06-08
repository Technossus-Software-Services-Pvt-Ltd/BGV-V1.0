# Python Tech Debt Audit - v6

**Date:** 2026-06-02  
**Auditor:** Principal Python Architect / Staff Security Engineer  
**Scope:** Full backend codebase (`backend/app/`, `backend/tests/`)  
**Stack:** Python 3.11+, FastAPI, SQLAlchemy Async, Pydantic v2, PaddleOCR, Ollama LLM  

---

## 1. 📁 File-Level Tech Debt

---

### File: `backend/app/main.py`

#### Function/Class: `_recover_stuck_documents()`
**Line:** 44-67  
**Severity:** 🔴 P0

❌ **Issue:**  
`pg_advisory_lock(42)` is used during startup but the application startup also runs `Base.metadata.create_all` for development which uses SQLite in tests. This recovery function will crash in non-PostgreSQL environments (e.g., tests using SQLite) because `pg_advisory_lock` is a PostgreSQL-only function.

🔍 **Root Cause:**  
No database dialect check before issuing PostgreSQL-specific SQL.

⚠ **Production Impact:**  
In production with PostgreSQL this works fine. However, any multi-database testing or migration to another DB will crash on startup.

🏗 **Category:** Architecture / Portability

👉 **Suggested Fix:**
```python
async def _recover_stuck_documents():
    from sqlalchemy import update, text
    from app.db.session import AsyncSessionLocal
    from app.models.document import Document
    from app.models.enums import ProcessingStatus
    from app.core.logging import get_logger

    logger = get_logger("startup.recovery")
    stuck_states = [...]

    async with AsyncSessionLocal() as db:
        # Only use advisory lock on PostgreSQL
        dialect = db.bind.dialect.name if db.bind else ""
        if dialect == "postgresql":
            await db.execute(text("SELECT pg_advisory_lock(42)"))
        try:
            result = await db.execute(
                update(Document)
                .where(Document.processing_status.in_(stuck_states))
                .values(processing_status=ProcessingStatus.UPLOADED.value)
            )
            if result.rowcount:
                logger.warning("recovered_stuck_documents", count=result.rowcount)
            await db.commit()
        finally:
            if dialect == "postgresql":
                await db.execute(text("SELECT pg_advisory_unlock(42)"))
                await db.commit()
```

---

#### Function/Class: `catch_unhandled_exceptions` middleware
**Line:** 121-135  
**Severity:** 🟠 P1

❌ **Issue:**  
The middleware catches `BGVBaseException` and re-raises it, but FastAPI's exception handler runs BEFORE middleware in the stack. The `isinstance(exc, BGVBaseException)` check and re-raise in the middleware will never be triggered because the exception handler already handles it. If for some reason it did trigger, re-raising inside middleware causes undefined behavior (the response is already being streamed).

🔍 **Root Cause:**  
Misunderstanding of FastAPI/Starlette request lifecycle. Exception handlers run at the ASGI app level before response streaming, while middleware wraps `call_next` which returns a streaming response.

⚠ **Production Impact:**  
Low immediate risk since the path is unreachable, but the dead code creates confusion during debugging.

🏗 **Category:** Architecture

👉 **Suggested Fix:**  
Remove the `isinstance(exc, BGVBaseException)` check — it's dead code. The middleware only receives exceptions that bubble past all exception handlers (truly unhandled ones).

---

### File: `backend/app/core/config.py`

#### Function/Class: `Settings._validate_required_settings()`
**Line:** 83-101  
**Severity:** 🟠 P1

❌ **Issue:**  
The `model_validator` mutates `self` (assigning `self.database_url`, `self.secret_key`) inside an `after` validator. Pydantic v2 validators with `mode="after"` can mutate, but this pattern is fragile — any future `frozen=True` model config will break it silently.

🔍 **Root Cause:**  
Mixing validation with default generation. Should use `@field_validator` with `default` factory or environment variable defaults.

⚠ **Production Impact:**  
Functional but fragile. If model becomes frozen in future, mutation fails silently.

🏗 **Category:** Architecture / Maintainability

👉 **Refactoring Approach:**  
Use `model_validator(mode="before")` or separate factory defaults from validation.

---

### File: `backend/app/core/security.py`

✅ No issues found in this file. Good magic-bytes validation, filename sanitization, and size checks.

---

### File: `backend/app/core/logging.py`

✅ No issues found in this file. Proper structlog configuration with environment-aware rendering.

---

### File: `backend/app/core/exceptions.py`

✅ No issues found in this file. Clean exception hierarchy with proper HTTP status mapping.

---

### File: `backend/app/db/session.py`

#### Function/Class: `get_db()`
**Line:** 20-27  
**Severity:** 🟡 P2

❌ **Issue:**  
The generator does not commit on success. Each route that wants to persist data must call `await db.commit()` explicitly. While this is a valid "unit of work" pattern, it's inconsistent — some routes commit, but if a route forgets to commit, data is silently lost.

🔍 **Root Cause:**  
No auto-commit-on-success pattern. The session closes without committing pending changes.

⚠ **Production Impact:**  
Potential silent data loss if a developer forgets to commit in a new route.

🏗 **Category:** Architecture

👉 **Refactoring Approach:**  
Consider a wrapper that commits on success:
```python
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

### File: `backend/app/db/session.py`

#### Function/Class: `engine` (module-level)
**Line:** 4-10  
**Severity:** 🟡 P2

❌ **Issue:**  
`pool_size=5` and `max_overflow=10` are hardcoded rather than configurable via settings. Under load with multiple background tasks, the pool may be exhausted.

🔍 **Root Cause:**  
No configuration surface for connection pool tuning.

⚠ **Production Impact:**  
Pool exhaustion under concurrent batch + document processing + API requests.

🏗 **Category:** Configuration / Scalability

👉 **Suggested Fix:**  
Add `db_pool_size` and `db_max_overflow` to `Settings` and wire them into the engine constructor.

---

### File: `backend/app/api/deps.py`

#### Function/Class: `get_current_user()`
**Line:** 28-79  
**Severity:** 🟠 P1

❌ **Issue:**  
Session tokens are looked up by exact string match (`AuthSession.session_token == token`). Tokens are stored in plaintext in the database. If the database is compromised, all active sessions are immediately usable by an attacker.

🔍 **Root Cause:**  
Session tokens stored in cleartext rather than hashed. The `AuthSession` model does encrypt `access_token` and `refresh_token` via Fernet, but the `session_token` itself is stored raw.

⚠ **Production Impact:**  
🔐 **Security:** Database breach exposes all active session tokens, allowing session hijacking without knowing the secret key.

🏗 **Category:** Security

👉 **Suggested Fix:**  
Store `SHA-256(session_token)` in the database. On lookup, hash the incoming token and compare:
```python
import hashlib
token_hash = hashlib.sha256(token.encode()).hexdigest()
# Query: AuthSession.session_token_hash == token_hash
```

---

### File: `backend/app/api/routes/upload.py`

#### Function/Class: `upload_documents()`
**Line:** 28-30  
**Severity:** 🟠 P1

❌ **Issue:**  
Legacy `_processing_semaphore` and `_inflight_tasks` are still defined at module level (lines 28-30) but never used — the code correctly uses `task_manager.submit()` below. These are dead code.

🔍 **Root Cause:**  
Incomplete cleanup after migrating to centralized TaskManager.

⚠ **Production Impact:**  
No runtime impact, but creates confusion and misleads developers into thinking there are two concurrency control mechanisms.

🏗 **Category:** Maintainability

👉 **Suggested Fix:**  
Remove lines 28-30 (`_processing_semaphore`, `_inflight_tasks`) and the `_handle_task_exception` function (lines 34-40).

---

#### Function/Class: `upload_documents()`
**Line:** 116-118  
**Severity:** 🟡 P2

❌ **Issue:**  
`validate_file_content` is called with padded bytes (`header_bytes + b"\x00" * max(0, 2048 - len(header_bytes))`) — null bytes are appended to reach 2048 bytes. This can confuse magic-bytes detection for formats that interpret trailing nulls differently.

🔍 **Root Cause:**  
Workaround for streaming upload where only the first chunk's header is available for content-type detection.

⚠ **Production Impact:**  
Edge case: files whose magic bytes are beyond the first chunk boundary may not be validated correctly.

🏗 **Category:** Validation

👉 **Suggested Fix:**  
Pass only `header_bytes` (without padding) to `validate_file_content` and ensure `_detect_mime_from_magic_bytes` handles shorter buffers gracefully (it already does at line 20 of security.py).

---

### File: `backend/app/api/routes/auth.py`

#### Function/Class: `google_auth_callback()`
**Line:** 157-200  
**Severity:** 🟠 P1

❌ **Issue:**  
The `httpx.AsyncClient` is created and destroyed per request (`async with httpx.AsyncClient(timeout=30.0) as client:`). This means a new TCP connection + TLS handshake is made for every OAuth callback. While not high-frequency, it wastes resources and adds latency.

🔍 **Root Cause:**  
No reusable HTTP client for Google OAuth token exchange.

⚠ **Production Impact:**  
~200ms additional latency per OAuth callback due to connection setup.

🏗 **Category:** Performance

👉 **Refactoring Approach:**  
Use a module-level `httpx.AsyncClient` (like `OllamaClient` does) and close it during app shutdown.

---

#### Function/Class: `google_auth_callback()` (session creation)
**Line:** 220+  
**Severity:** 🟠 P1

❌ **Issue:**  
No rate limiting on the OAuth callback endpoint. An attacker who obtains a valid authorization code could replay it before the state is consumed (race condition window between state lookup and deletion).

🔍 **Root Cause:**  
State deletion (`await db.delete(oauth_state)`) and code exchange are not atomic. Two concurrent requests with the same state could both pass the validation.

⚠ **Production Impact:**  
🔐 **Security:** Theoretical TOCTOU race condition on OAuth state consumption under concurrent requests.

🏗 **Category:** Security

👉 **Suggested Fix:**  
Use `SELECT ... FOR UPDATE` when fetching the OAuth state to create a row-level lock:
```python
result = await db.execute(
    select(OAuthState).where(OAuthState.state == payload.state).with_for_update()
)
```

---

### File: `backend/app/api/routes/batch.py`

#### Function/Class: `upload_batch_file()`
**Line:** 64  
**Severity:** 🟠 P1

❌ **Issue:**  
`file_bytes = await file.read()` reads the entire import file into memory before size-checking. The size check at line 65 (`if len(file_bytes) > 10 * 1024 * 1024`) happens AFTER the file is already in memory. A 100MB+ file will consume 100MB of RAM before being rejected.

🔍 **Root Cause:**  
Size check is post-read rather than streaming-based.

⚠ **Production Impact:**  
Memory spike / potential OOM if multiple large files are uploaded concurrently.

🏗 **Category:** Performance / Memory

👉 **Suggested Fix:**  
Check `file.size` (if available from the multipart header) before reading, or stream with a byte counter:
```python
chunks = []
total = 0
MAX_IMPORT_SIZE = 10 * 1024 * 1024
async for chunk in file:
    total += len(chunk)
    if total > MAX_IMPORT_SIZE:
        raise HTTPException(status_code=400, detail="Import file must be under 10MB")
    chunks.append(chunk)
file_bytes = b"".join(chunks)
```

---

#### Function/Class: `list_batch_imports()`
**Line:** 175-189  
**Severity:** 🟡 P2

❌ **Issue:**  
Date parsing uses `datetime.strptime` with a bare `try/except ValueError: pass` — silently ignores invalid dates without informing the client.

🔍 **Root Cause:**  
Inconsistency with other routes that use `parse_date_param()` which raises HTTP 400.

⚠ **Production Impact:**  
Silent filter bypass — client sends bad date, gets unfiltered results without knowing.

🏗 **Category:** Validation / API Design

👉 **Suggested Fix:**  
Use the existing `parse_date_param()` utility from `app.api.utils`.

---

### File: `backend/app/api/routes/documents.py`

#### Function/Class: `list_documents()`
**Line:** 61-69  
**Severity:** 🟡 P2

❌ **Issue:**  
The validation enrichment loop uses `val_map` which is defined inside a conditional (`if doc_ids:`) block, but is referenced outside that block at line 73 (`val = val_map.get(doc.id) if doc_ids else None`). If `doc_ids` is empty, `val_map` is undefined → `NameError` at runtime.

🔍 **Root Cause:**  
Variable scoping issue — `val_map` only defined inside the `if doc_ids` block.

⚠ **Production Impact:**  
Runtime crash when the query returns no documents (empty state). However, the `if doc_ids else None` guard on line 73 prevents accessing `val_map` when `doc_ids` is falsy, so this is actually safe. But `val_map` is still referenced in scope — fragile.

🏗 **Category:** Maintainability

👉 **Suggested Fix:**  
Initialize `val_map = {}` before the `if doc_ids:` block.

---

#### Function/Class: `get_document_detail()`
**Line:** 86-100  
**Severity:** 🟡 P2

❌ **Issue:**  
`asyncio.gather` is used with multiple DB queries on the SAME session. SQLAlchemy AsyncSession is NOT safe for concurrent operations on the same session — it can cause "session is already in a transaction" errors or corrupted state.

🔍 **Root Cause:**  
`asyncio.gather` runs coroutines concurrently, but all coroutines share the same `db` session which is not thread/task-safe for concurrent queries.

⚠ **Production Impact:**  
Under SQLAlchemy async with asyncpg, concurrent `execute()` on the same session raises `InvalidRequestError`. This likely works only because asyncpg serializes under the hood in some cases, but is undefined behavior.

🏗 **Category:** Async / Architecture

👉 **Suggested Fix:**  
Execute queries sequentially on the same session, or create separate sessions per query:
```python
pages_result = await db.execute(...)
ocr_result = await db.execute(...)
# Sequential is safe with a single session
```

---

### File: `backend/app/api/routes/dashboard.py`

#### Function/Class: `get_dashboard_stats()`
**Line:** 36-39  
**Severity:** 🟡 P2

❌ **Issue:**  
The cache check (line 37) is done outside the lock (lock-free fast path), but the cache write (line 128-130) is inside the lock. This is a classic "check-then-act" race: two concurrent requests can both see an expired cache, both execute the full query, and both write to the cache. Not harmful (just wasted work) but the lock provides no real protection.

🔍 **Root Cause:**  
Double-checked locking pattern is incomplete — the fast path doesn't recheck after acquiring the lock.

⚠ **Production Impact:**  
Thundering herd on cache expiry — all concurrent requests will execute the expensive queries. For a 30s TTL dashboard endpoint, this is low-impact.

🏗 **Category:** Performance

👉 **Refactoring Approach:**  
Recheck the cache after acquiring the lock (standard double-checked locking):
```python
async with _dashboard_cache_lock:
    if _dashboard_cache["data"] is not None and time.time() < _dashboard_cache["expires_at"]:
        return _dashboard_cache["data"]
    # ... compute result ...
    _dashboard_cache["data"] = result
    _dashboard_cache["expires_at"] = time.time() + settings.dashboard_cache_ttl_seconds
```

---

### File: `backend/app/api/routes/ws.py`

#### Function/Class: `websocket_batch()`
**Line:** 77-135  
**Severity:** 🟡 P2

❌ **Issue:**  
The WebSocket disconnect handler does not call `ws_hub.disconnect()`, so the `_rooms` dict accumulates dead connections. Connections are only cleaned lazily during `broadcast()` when `send_text` fails.

🔍 **Root Cause:**  
Missing explicit disconnect call in the `except WebSocketDisconnect` block.

⚠ **Production Impact:**  
Memory leak — dead WebSocket references accumulate in `_rooms` until the next broadcast attempt cleans them up. For long-lived batches with no broadcasts, these accumulate indefinitely.

🏗 **Category:** Memory Leak

👉 **Suggested Fix:**
```python
except WebSocketDisconnect:
    await ws_hub.disconnect(websocket, batch_id)
except Exception as e:
    logger.warning("ws_error", batch_id=batch_id, error=str(e))
    await ws_hub.disconnect(websocket, batch_id)
```

---

### File: `backend/app/api/routes/settings.py`

#### Function/Class: `gmail_oauth_callback()`
**Line:** 40  
**Severity:** 🟡 P2

❌ **Issue:**  
`os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")` is set at module import time based on `settings.environment`. This pollutes the process environment permanently and cannot be undone. If the settings change at runtime (unlikely but possible via env reload), the flag persists.

🔍 **Root Cause:**  
Module-level side effect that cannot be reversed.

⚠ **Production Impact:**  
Low — only affects development. But if `environment` is accidentally set wrong, HTTPS validation for OAuth would be disabled in production.

🏗 **Category:** Security / Configuration

👉 **Suggested Fix:**  
Move this into a function that's called explicitly, or add an assertion:
```python
if app_settings.environment == "development":
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
else:
    assert os.environ.get("OAUTHLIB_INSECURE_TRANSPORT") != "1", "OAUTHLIB_INSECURE_TRANSPORT must not be set in production"
```

---

### File: `backend/app/services/task_manager.py`

#### Function/Class: `TaskManager.submit()`
**Line:** 84  
**Severity:** 🟠 P1

❌ **Issue:**  
`task._task_type = task_type` sets a private attribute on `asyncio.Task`. This is implementation-dependent and could break with future Python versions. Additionally, `asyncio.Task` does not guarantee attribute persistence across serialization boundaries.

🔍 **Root Cause:**  
No proper mechanism to associate metadata with asyncio tasks.

⚠ **Production Impact:**  
Works currently, but fragile. Could break on Python upgrades.

🏗 **Category:** Anti-pattern

👉 **Suggested Fix:**  
Use a separate `dict[asyncio.Task, TaskType]` mapping:
```python
self._task_types: dict[asyncio.Task, TaskType] = {}

# In submit:
self._task_types[task] = task_type

# In _on_task_done:
self._task_types.pop(task, None)
```

---

### File: `backend/app/services/processing/pipeline.py`

#### Function/Class: `ProcessingPipeline` (class-level singletons)
**Line:** 53-59  
**Severity:** 🟠 P1

❌ **Issue:**  
Class-level singletons (`_ocr_engine = PaddleOCREngine()`, etc.) are created at import time. This means PaddleOCR is initialized when the module is first imported (e.g., during test collection), even if it's never used. This adds significant startup time and memory usage.

🔍 **Root Cause:**  
Eager initialization at class definition time instead of lazy initialization.

⚠ **Production Impact:**  
~2-5 seconds of startup delay + ~500MB memory from PaddleOCR model loading, even for routes that don't need OCR. Also affects test startup time.

🏗 **Category:** Performance / Architecture

👉 **Suggested Fix:**  
The `dependencies.py` module already provides singleton instances via `_ocr_engine = PaddleOCREngine()`. The class-level singletons in `ProcessingPipeline` are redundant. Remove them and always inject dependencies:
```python
class ProcessingPipeline:
    def __init__(self, db: AsyncSession, *, ocr_engine: PaddleOCREngine, ...):
        # Remove fallback to class-level singletons
        self.ocr_engine = ocr_engine
        ...
```

---

### File: `backend/app/services/dependencies.py`

#### Function/Class: Module-level singletons
**Line:** 32-38  
**Severity:** 🟠 P1

❌ **Issue:**  
Same issue as pipeline.py — `_ocr_engine = PaddleOCREngine()` at module level triggers PaddleOCR initialization at import time. Since `dependencies.py` is imported by route modules, this happens on application startup regardless of whether OCR is needed.

🔍 **Root Cause:**  
Eager instantiation. PaddleOCR loads ML models on `__init__`.

⚠ **Production Impact:**  
Increased startup time and baseline memory usage. In practice, the `PaddleOCREngine.__init__` doesn't load models (lazy via `_get_paddle_ocr()`), so this specific instance is actually lightweight. However, if any singleton's `__init__` becomes expensive, it will block startup.

🏗 **Category:** Architecture

👉 **Refactoring Approach:**  
Use `functools.lru_cache` or `@cache` for lazy singleton creation:
```python
from functools import cache

@cache
def get_ocr_engine() -> PaddleOCREngine:
    return PaddleOCREngine()
```

---

### File: `backend/app/services/ai/ollama_client.py`

#### Function/Class: `OllamaClient.generate()`
**Line:** 51-110  
**Severity:** 🟡 P2

❌ **Issue:**  
The `generate()` method catches ALL exceptions and returns an `OllamaResponse` with an error field instead of raising. This means callers must always check `response.is_successful` — a forgotten check silently swallows errors. The `AIClassifier` does check this, but the pattern is error-prone for future callers.

🔍 **Root Cause:**  
Error-as-value pattern instead of exception-based error propagation.

⚠ **Production Impact:**  
If a new caller forgets to check `is_successful`, classification silently fails with empty content treated as valid.

🏗 **Category:** Anti-pattern / Error Handling

👉 **Refactoring Approach:**  
Consider raising `OllamaConnectionError` on connection failures and returning error responses only for non-critical parse issues. Alternatively, document the contract explicitly and add a `raise_for_status()` helper.

---

### File: `backend/app/services/ocr/engine.py`

#### Function/Class: `PaddleOCREngine.process()` and `process_from_path()`
**Line:** 88-200  
**Severity:** 🟡 P2

❌ **Issue:**  
Massive code duplication between `process()` (takes np.ndarray) and `process_from_path()` (takes Path). The entire result-parsing logic (lines 95-145 and 165-200) is duplicated verbatim.

🔍 **Root Cause:**  
Two entry points added independently without extracting shared logic.

⚠ **Production Impact:**  
Bugs fixed in one method may not be fixed in the other. Maintenance burden.

🏗 **Category:** DRY / Duplication

👉 **Suggested Fix:**  
Extract result parsing into a private method:
```python
def _parse_ocr_results(self, results, start_time: float) -> OCREngineResult:
    # ... shared parsing logic ...
```

---

### File: `backend/app/services/batch/orchestrator.py`

#### Function/Class: `BatchOrchestrator._process_candidate()`
**Line:** 152-210  
**Severity:** 🟠 P1

❌ **Issue:**  
Inline imports inside the loop body (`from app.services.batch.ingest_service import _io_executor`) on every iteration. This is repeated for each Gmail attachment AND each Drive file. While Python caches imports, accessing a module's private `_io_executor` from outside its module violates encapsulation.

🔍 **Root Cause:**  
The orchestrator duplicates download logic that should be delegated to `DocumentIngestService`. The `ingest_service._save_document()` is called directly using a private method.

⚠ **Production Impact:**  
Tight coupling to implementation details of `ingest_service`. If `_io_executor` is renamed or moved, this breaks at runtime (no static analysis catches it).

🏗 **Category:** Architecture / Coupling

👉 **Suggested Fix:**  
Delegate the full download+save workflow to `DocumentIngestService.download_and_save()` which already exists and encapsulates this logic. The orchestrator should call:
```python
document_ids, failed = await self._ingest.download_and_save(
    candidate, upload_batch, gmail_scanner, drive_service,
    gmail_attachments, drive_files, batch.correlation_id,
)
```

---

#### Function/Class: `BatchOrchestrator.process_batch()`
**Line:** 70-100  
**Severity:** 🟠 P1

❌ **Issue:**  
The entire batch is processed sequentially within a single database session. If processing 50 candidates takes 30 minutes, the session is held open the entire time. Any connection pool timeout or network blip will kill the session and lose all progress.

🔍 **Root Cause:**  
No session-per-candidate isolation. One long-lived session for the entire batch.

⚠ **Production Impact:**  
Database connection exhaustion during large batches. Connection timeouts losing progress. No ability to resume from last successful candidate.

🏗 **Category:** Scalability / Resilience

👉 **Refactoring Approach:**  
Use a session-per-candidate pattern:
```python
for idx, bc in enumerate(candidates, start=1):
    async with AsyncSessionLocal() as candidate_db:
        await self._process_candidate_isolated(candidate_db, batch_id, bc.id, ...)
```

---

### File: `backend/app/services/batch/ingest_service.py`

#### Function/Class: `DocumentIngestService.download_and_save()`
**Line:** 55-93  
**Severity:** 🟡 P2

❌ **Issue:**  
The method re-raises exceptions after incrementing `failed_count`, but the `except` block does `raise` — so `failed_count` is never returned to the caller since the exception propagates. The `failed_count` variable is effectively dead.

🔍 **Root Cause:**  
Logic error: counting failures AND re-raising makes the count useless.

⚠ **Production Impact:**  
If any single download fails, the entire batch candidate fails. No partial progress tracking.

🏗 **Category:** Error Handling

👉 **Suggested Fix:**  
Either collect errors and continue (fault-tolerant), or don't maintain `failed_count`:
```python
except Exception as e:
    failed_count += 1
    logger.error("gmail_download_failed", filename=att.filename, error=str(e))
    # Don't re-raise — continue with next attachment
```

---

#### Function/Class: Module-level duplicate import
**Line:** 21-22  
**Severity:** 🟡 P2

❌ **Issue:**  
`from app.core.config import settings` is imported twice (lines 20 and 21).

🔍 **Root Cause:**  
Copy-paste error.

⚠ **Production Impact:**  
None — Python deduplicates imports. But it's a code smell.

🏗 **Category:** Maintainability

👉 **Suggested Fix:**  
Remove the duplicate import on line 21.

---

### File: `backend/app/services/batch/discovery_service.py`

#### Function/Class: `DiscoveryService.discover_documents()`
**Line:** 87-99  
**Severity:** 🟡 P2

❌ **Issue:**  
The Drive search is never actually executed — `drive_files` is always returned as an empty list (`drive_files: list[DiscoveredDriveFile] = []`). The `drive_service` parameter is accepted but never used.

🔍 **Root Cause:**  
Incomplete implementation — Drive discovery was never wired up in this service. The orchestrator handles Drive discovery directly in `_process_candidate`.

⚠ **Production Impact:**  
Drive discovery only works because the orchestrator bypasses this service. The service's contract is misleading.

🏗 **Category:** Architecture / Incomplete

👉 **Suggested Fix:**  
Either implement Drive discovery in this service (and have orchestrator call it), or remove the `drive_service` parameter and document that Drive discovery happens elsewhere.

---

### File: `backend/app/services/notifications/email_service.py`

#### Function/Class: `NotificationService.send_notifications_background()`
**Line:** 155-180  
**Severity:** 🟠 P1

❌ **Issue:**  
The background task creates its own `AsyncSessionLocal()` session and holds it for the entire notification send loop. If sending 100 emails with retries takes 10+ minutes, the DB connection is held open the entire time.

🔍 **Root Cause:**  
Same long-lived session anti-pattern as the batch orchestrator.

⚠ **Production Impact:**  
Connection pool exhaustion under bulk notification scenarios.

🏗 **Category:** Scalability

👉 **Suggested Fix:**  
Open a new session per notification (or per small batch of notifications).

---

### File: `backend/app/services/integrations/drive_service.py`

#### Function/Class: `GoogleDriveService.search_for_candidate()`
**Line:** 95  
**Severity:** 🟠 P1

❌ **Issue:**  
The search query uses `name contains '{self._escape_query(term)}'` — but `_escape_query` is called but never defined in the visible code. If it doesn't exist, this will throw `AttributeError` at runtime.

🔍 **Root Cause:**  
Missing method or method defined below the visible section.

⚠ **Production Impact:**  
Runtime crash on any Drive search.

🏗 **Category:** Bug

👉 **Suggested Fix:**  
Ensure `_escape_query` exists and properly escapes single quotes:
```python
@staticmethod
def _escape_query(term: str) -> str:
    return term.replace("\\", "\\\\").replace("'", "\\'")
```

---

### File: `backend/app/services/websocket/hub.py`

✅ No issues found. Clean asyncio lock usage, proper dead connection cleanup.

---

### File: `backend/app/services/audit/logger.py`

✅ No issues found. Good PII masking implementation.

---

### File: `backend/app/services/validation/ownership.py`

✅ No issues found. Well-structured scoring with clear thresholds.

---

### File: `backend/app/services/batch/parser.py`

✅ No issues found. Proper input validation, encoding handling, and column aliasing.

---

### File: `backend/app/services/batch/checklist_matcher.py`

✅ No issues found. Clean stateless utility with substring matching.

---

### File: `backend/app/services/ai/classifier.py`

#### Function/Class: `AIClassifier.__init__()`
**Line:** 48  
**Severity:** 🟡 P2

❌ **Issue:**  
A new `OllamaClient()` is created per `AIClassifier` instance if no client is injected. Since `AIClassifier` is used as a singleton in `dependencies.py`, this is fine in practice. However, if someone creates a temporary `AIClassifier()`, they get an `OllamaClient` with its own HTTP connection pool that's never closed.

🔍 **Root Cause:**  
Default argument creates owned resource without cleanup responsibility.

⚠ **Production Impact:**  
Potential connection leaks if `AIClassifier` is instantiated in tests or one-off scripts.

🏗 **Category:** Resource Management

👉 **Suggested Fix:**  
Make the `client` parameter required or use the shared instance from `dependencies.py`.

---

### File: `backend/app/models/auth_session.py`

#### Function/Class: `_get_fernet()`
**Line:** 16-18  
**Severity:** 🟡 P2

❌ **Issue:**  
`hashlib.sha256(settings.secret_key.encode()).digest()` is used to derive a Fernet key. SHA-256 is not a proper KDF — it provides no salt, no iteration count, and no protection against brute-force. For encrypting OAuth tokens at rest, this is acceptable but not ideal.

🔍 **Root Cause:**  
Using raw hash as key derivation instead of PBKDF2/scrypt/argon2.

⚠ **Production Impact:**  
If the secret_key has low entropy, the derived key is vulnerable to brute-force. Since `secret_key` is generated via `secrets.token_urlsafe(32)` in dev, this is mitigated.

🏗 **Category:** Security (Low severity given strong key generation)

👉 **Refactoring Approach:**  
Use `PBKDF2HMAC` from cryptography:
```python
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"bgv-token-enc", iterations=100_000)
```

---

### File: `backend/app/api/routes/health.py`

#### Function/Class: `_ollama_client` (module-level)
**Line:** 5  
**Severity:** 🟡 P2

❌ **Issue:**  
A separate `OllamaClient()` instance is created just for health checks. This creates an additional HTTP connection pool independent of the one used by `AIClassifier`. Two connection pools to the same Ollama service is wasteful.

🔍 **Root Cause:**  
No shared `OllamaClient` singleton accessible to the health route.

⚠ **Production Impact:**  
Wasted resources (extra connection pool), and health check may show "healthy" even if the classifier's client is broken.

🏗 **Category:** Architecture / DRY

👉 **Suggested Fix:**  
Use the shared instance from `dependencies.py`:
```python
from app.services.dependencies import get_ai_classifier
_ollama_client = get_ai_classifier().client
```

---

### File: `backend/app/services/processing/stages/ocr_stage.py`

#### Function/Class: `OCRStage._process_page_ocr()`
**Line:** 99-102  
**Severity:** 🟡 P2

❌ **Issue:**  
`loop.run_in_executor(None, self.preprocessor.normalize_image, page_path)` uses the default executor (which is a shared thread pool). CPU-intensive image preprocessing shares the same executor as other `run_in_executor` calls. For OCR itself, a dedicated `_ocr_executor` is used, but preprocessing uses the default.

🔍 **Root Cause:**  
Inconsistent executor usage between preprocessing (default) and OCR (dedicated).

⚠ **Production Impact:**  
Under load, image preprocessing can starve other `run_in_executor` operations (like `asyncio.to_thread` calls elsewhere).

🏗 **Category:** Performance

👉 **Suggested Fix:**  
Use the same dedicated `_ocr_executor` from `engine.py` for preprocessing, or create a separate CPU-bound pool.

---

### File: `backend/tests/conftest.py`

#### Function/Class: `client` fixture
**Line:** 35-65  
**Severity:** 🟠 P1

❌ **Issue:**  
The test fixture does NOT mock `get_current_user`, meaning all authenticated endpoints return 401 in tests. This is documented as a known issue (23 test failures), but it makes the test suite unreliable for CI/CD.

🔍 **Root Cause:**  
Missing auth override in test fixtures.

⚠ **Production Impact:**  
Test suite cannot validate authenticated endpoint behavior. Regressions in auth-protected routes go undetected.

🏗 **Category:** Testing

👉 **Suggested Fix:**
```python
from app.api.deps import get_current_user
from app.models.auth_user import AuthUser

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return AuthUser(id="test-user-id", email="test@example.com", name="Test User", is_active=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    ...
```

---

### File: `backend/app/models/candidate.py`

#### Function/Class: `Candidate` model
**Line:** 12-14  
**Severity:** 🟡 P2

❌ **Issue:**  
PII fields (`email`, `phone`, `dob`) are stored in plaintext in the database. The audit service masks PII in logs, but the actual data remains unencrypted at rest. For a Background Verification platform handling sensitive personal data, this is a compliance concern.

🔍 **Root Cause:**  
No field-level encryption for PII columns.

⚠ **Production Impact:**  
Database breach exposes all candidate PII (email, phone, DOB). May violate GDPR/DPDPA requirements.

🏗 **Category:** Security / Compliance

👉 **Refactoring Approach:**  
Apply application-level encryption (similar to `AuthSession._access_token`) for PII fields, or use PostgreSQL's pgcrypto extension for column-level encryption.

---

### File: `backend/app/api/routes/candidates.py`

#### Function/Class: `get_candidate()`
**Line:** 69-73  
**Severity:** 🟡 P2

❌ **Issue:**  
The query uses `(Candidate.id == candidate_id) | (Candidate.candidate_id == candidate_id)` — accepts both internal UUID and external candidate_id in the same parameter. This means if an external candidate_id happens to be a valid UUID that matches another candidate's internal ID, wrong data is returned.

🔍 **Root Cause:**  
Overloaded path parameter semantics.

⚠ **Production Impact:**  
Data confusion in edge cases where external IDs look like UUIDs.

🏗 **Category:** API Design

👉 **Suggested Fix:**  
Use separate endpoints or validate the format:
```python
# If it looks like a UUID, search by internal ID; otherwise by candidate_id
try:
    uuid.UUID(candidate_id)
    filter_clause = Candidate.id == candidate_id
except ValueError:
    filter_clause = Candidate.candidate_id == candidate_id
```

---

## 2. 🔁 Duplication Report

| Pattern | Locations | Impact |
|---------|-----------|--------|
| OCR result parsing logic | `engine.py:process()` + `engine.py:process_from_path()` | Bug fixes must be applied twice |
| `OllamaClient` instantiation | `health.py`, `classifier.py`, `dependencies.py` | 3 separate HTTP pools to same service |
| Download + save logic | `orchestrator.py:_process_candidate()` + `ingest_service.py:download_and_save()` | Orchestrator bypasses the service it should use |
| Date parsing | `batch.py` (manual strptime) vs `documents.py`/`processing.py` (parse_date_param) | Inconsistent error handling |
| `_io_executor` ThreadPoolExecutor | `discovery_service.py` + `ingest_service.py` | Two separate thread pools for same purpose |
| Candidate upsert logic | `upload.py:upload_documents()` + `orchestrator.py:_ensure_candidate()` | Divergent "get or create" patterns |
| Task submission pattern | Used identically across `upload.py`, `batch.py`, `review_queue.py` | Not an issue (correct usage of TaskManager) |

---

## 3. 🚨 Critical Tech Debt (P0)

| # | Issue | File | Impact |
|---|-------|------|--------|
| 1 | Session tokens stored in plaintext | `api/deps.py` | DB breach → full session hijack |
| 2 | `asyncio.gather` on shared SQLAlchemy session | `api/routes/documents.py:86-100` | Undefined behavior / potential crash |
| 3 | `pg_advisory_lock` in non-PG environments | `main.py:60-66` | Startup crash in non-PostgreSQL environments |

---

## 4. ⚠️ High & Medium Debt

### High (P1)

| # | Issue | File |
|---|-------|------|
| 1 | Session token not hashed in DB | `api/deps.py` |
| 2 | OAuth state TOCTOU race condition | `api/routes/auth.py` |
| 3 | Batch file read-all-then-check-size | `api/routes/batch.py:64` |
| 4 | Long-lived DB session in batch processing | `services/batch/orchestrator.py` |
| 5 | Long-lived DB session in notifications | `services/notifications/email_service.py` |
| 6 | Private attribute on asyncio.Task | `services/task_manager.py:84` |
| 7 | Orchestrator bypasses IngestService | `services/batch/orchestrator.py:152-210` |
| 8 | Class-level singleton eager init | `services/processing/pipeline.py:53-59` |
| 9 | Test suite missing auth mock (23 failures) | `tests/conftest.py` |
| 10 | `_escape_query` possibly missing | `services/integrations/drive_service.py:95` |
| 11 | httpx client per OAuth callback | `api/routes/auth.py:157` |

### Medium (P2)

| # | Issue | File |
|---|-------|------|
| 1 | No auto-commit in `get_db` | `db/session.py` |
| 2 | Hardcoded pool size | `db/session.py` |
| 3 | WebSocket leak (no disconnect call) | `api/routes/ws.py` |
| 4 | Dashboard cache thundering herd | `api/routes/dashboard.py` |
| 5 | Duplicate OCR parsing code | `services/ocr/engine.py` |
| 6 | Dead code (_processing_semaphore) | `api/routes/upload.py:28-30` |
| 7 | Null-padded bytes in validation | `api/routes/upload.py:116-118` |
| 8 | Silent date parse errors in batch list | `api/routes/batch.py:175-189` |
| 9 | `val_map` scoping fragility | `api/routes/documents.py:61` |
| 10 | Candidate PII stored unencrypted | `models/candidate.py` |
| 11 | Duplicate `settings` import | `services/batch/ingest_service.py:21-22` |
| 12 | Discovery service never uses drive_service | `services/batch/discovery_service.py` |
| 13 | SHA-256 as KDF for Fernet | `models/auth_session.py:16` |
| 14 | OllamaClient duplicate in health route | `api/routes/health.py:5` |
| 15 | Preprocessing uses default executor | `services/processing/stages/ocr_stage.py:99` |
| 16 | Middleware dead code path | `main.py:125` |
| 17 | Error-as-value pattern in OllamaClient | `services/ai/ollama_client.py:51` |

---

## 5. 💡 Strategic Improvements

### 1. Session-Per-Unit-of-Work for Background Tasks
All background processors (batch orchestrator, notification sender) should create a fresh DB session per logical unit (per candidate, per notification batch) instead of holding one session for the entire operation.

### 2. Proper Task Queue (Phase 5)
Replace `asyncio.create_task` with a durable task queue (Celery + Redis, or arq). Benefits:
- Survives process crashes (tasks are persisted)
- Horizontal scaling (multiple workers)
- Retry with backoff built-in
- Dead letter queues for permanently failed tasks
- Observable via Flower/dashboard

### 3. OpenTelemetry Integration
Add distributed tracing:
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
```
This provides end-to-end visibility across upload → OCR → AI → validation.

### 4. Connection Pool Monitoring
Add pool event listeners to detect exhaustion before it causes failures:
```python
from sqlalchemy import event
@event.listens_for(engine.sync_engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    # Log pool stats
```

### 5. Rate Limiting
Add rate limiting to upload and auth endpoints:
- `/api/v1/upload`: 10 req/min per user
- `/api/v1/auth/google/callback`: 5 req/min per IP
- `/api/v1/batch/upload`: 5 req/min per user

### 6. Health Check Enhancement
The health endpoint should report:
- Database connectivity (with query latency)
- Connection pool utilization
- Active background task count
- Memory usage
- Ollama model loaded status

### 7. Graceful Degradation for AI Service
If Ollama is down, documents should be queued for retry rather than immediately failing. Add a circuit breaker pattern:
```python
from tenacity import CircuitBreaker
ai_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
```

### 8. Database Read Replicas
For the dashboard endpoint (heavy read queries), route to a read replica to avoid contending with write operations.

---

## 6. 📊 Python Quality Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| Naming | 88/100 | Clear, consistent naming throughout |
| Architecture | 72/100 | Good stage decomposition but coupling in orchestrator |
| Type Safety | 80/100 | Pydantic used well, but some untyped dicts in services |
| Logging | 90/100 | Excellent structlog usage with context |
| Exception Handling | 78/100 | Good hierarchy but error-as-value in OllamaClient |
| Async | 65/100 | Gather on shared session, long-lived sessions in background |
| API Design | 82/100 | RESTful, versioned, good status codes |
| Validation | 80/100 | Strong upload validation, weak in batch date parsing |
| Security | 62/100 | Plaintext session tokens, unencrypted PII, no rate limiting |
| DRY | 70/100 | OCR duplication, multiple OllamaClients, download logic |
| Performance | 75/100 | Good semaphore usage but pool/cache issues |
| Configuration | 85/100 | Pydantic Settings with env validation |
| Testing | 50/100 | 23 failing tests, missing auth mock |

**Python Score: 75/100**

---

## 7. 📉 Python Tech Debt Summary

| Metric | Count |
|--------|-------|
| **Total Issues** | 30 |
| 🔴 P0 (Critical) | 3 |
| 🟠 P1 (High) | 11 |
| 🟡 P2 (Medium) | 16 |
| **Duplication Cases** | 7 |

**Python Tech Debt Level: 🟡 Medium**

The codebase has solid foundations (good error hierarchy, structured logging, proper DI patterns, stage-based pipeline decomposition) but has accumulated security debt (plaintext tokens, unencrypted PII) and scalability gaps (long-lived sessions, no rate limiting) that need addressing before production hardening.

---

## 8. 🧾 Final Verdict

### ⚠️ Needs Improvement

**Justification:**

| Dimension | Assessment |
|-----------|------------|
| **Security** | Session tokens in plaintext and unencrypted PII are the most serious gaps. No rate limiting on auth endpoints creates abuse potential. |
| **Scalability** | Long-lived DB sessions in background tasks will exhaust connection pools under load. No durable task queue means work is lost on crash. |
| **Reliability** | 23 failing tests mean regressions go undetected. `asyncio.gather` on shared sessions is undefined behavior. |
| **Maintainability** | Good overall structure post-refactoring. Some coupling in orchestrator bypassing its own sub-services. |
| **Performance** | Adequate for current scale. Dashboard caching, OCR semaphores, and task manager provide reasonable throughput. Connection pool and executor sizing need tuning. |

**Priority Remediation Order:**
1. Hash session tokens (Security P0)
2. Fix `asyncio.gather` on shared session (Correctness P0)  
3. Add `get_current_user` mock to tests (Testing P1)
4. Session-per-candidate in batch orchestrator (Scalability P1)
5. Rate limiting on auth + upload (Security P1)
6. Encrypt candidate PII at rest (Compliance P2)
7. Implement durable task queue (Phase 5 - Resilience)
