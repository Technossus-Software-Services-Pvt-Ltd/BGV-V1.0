# Frontend Tech Debt Audit Report v10

**Date:** 2026-06-08  
**Auditor Role:** Principal Frontend Architect / Senior React Architect / UI Performance Engineer / Staff Security Engineer  
**Stack:** React 18, TypeScript, Vite, Tailwind CSS, Axios, React Router v6, Recharts, WebSocket  

---

## 1. 📁 File-Level Tech Debt

---

### File: `frontend/vite.config.ts`

✅ No issues found

---

### File: `frontend/tsconfig.json`

✅ No issues found

---

### File: `frontend/package.json`

✅ No issues found

---

### File: `frontend/tailwind.config.js`

✅ No issues found

---

### File: `frontend/.env`

✅ No issues found (non-sensitive configuration only)

---

### File: `frontend/src/main.tsx`

✅ No issues found

---

### File: `frontend/src/App.tsx`

✅ No issues found — Proper lazy loading, error boundary, route guards, and code splitting implemented.

---

### File: `frontend/src/hooks/useAuth.tsx`

✅ No issues found — Proper context pattern, memoized callbacks, cross-tab sync via StorageEvent, session expiry handling.

---

### File: `frontend/src/api/client.ts`

**Component/Hook:** `api` axios instance  
**Line:** 15-17  
**Severity:** 🟡 P2

❌ **Issue:**  
Module-level mutable variable `isHandling401` is used as a semaphore but never resets on navigation. The comment says "Flag resets on next full page load" — but in an SPA, full page loads are rare. If the user is redirected to /login and logs back in, the first successful response on line 20 resets the flag correctly, so the practical impact is limited. However, the pattern is fragile.

🔍 **Impact:**  
If the reset on success (line 20) is removed in a refactor, all 401 errors after the first would be silently swallowed.

🏗 **Category:** Architecture / Code Smell

👉 **Suggested Fix:**  
Reset `isHandling401 = false` explicitly during the login flow inside `AuthProvider.login()` or use an AbortController-based approach instead of a module flag.

---

### File: `frontend/src/api/endpoints.ts`

**Component/Hook:** `BatchLogItem` interface  
**Line:** 156-166  
**Severity:** 🟡 P2

❌ **Issue:**  
`BatchLogItem` interface is defined directly in the endpoints file rather than in `types/index.ts`. This creates a duplication pattern — the same interface shape (`BatchLogEntry`) already exists in `types/index.ts`.

🔍 **Impact:**  
Two nearly identical types (`BatchLogItem` in endpoints.ts and `BatchLogEntry` in types/index.ts) cause confusion and divergence risk.

🏗 **Category:** Architecture / DRY Violation

👉 **Suggested Fix:**  
Remove `BatchLogItem` from `endpoints.ts` and import `BatchLogEntry` from `types/index.ts`. Map the response if there are field differences.

---

### File: `frontend/src/utils/auth.ts`

✅ No issues found — Proper httpOnly cookie strategy, no token in localStorage, clear security documentation.

---

### File: `frontend/src/utils/formatting.ts`

**Component/Hook:** `statusColor`  
**Line:** 1-12  
**Severity:** 🟡 P2

❌ **Issue:**  
This function returns full Tailwind class strings. Both `statusColor` (in utils) and `statusConfig` (in `StatusBadge.tsx`) implement similar status-to-style mapping but with different class formats. Dual lookup patterns for the same concept.

🔍 **Impact:**  
Adding a new status requires updating both `StatusBadge` and `statusColor` utility. Easy to miss one.

🏗 **Category:** DRY Violation / Maintainability

👉 **Suggested Fix:**  
Consolidate into a single `STATUS_THEME` map exported from a shared module, used by both `StatusBadge` and inline status rendering. Example:

```typescript
// utils/statusTheme.ts
export const STATUS_THEME: Record<string, { classes: string; label: string }> = {
  completed: { classes: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/10', label: 'Completed' },
  // ...
};
```

---

### File: `frontend/src/services/websocket.ts`

**Component/Hook:** `BatchWebSocketService`  
**Line:** 166 (`_cleanup` method)  
**Severity:** 🟡 P2

❌ **Issue:**  
`_cleanup()` calls `this.handlers.clear()`, which removes ALL registered event handlers. If `disconnect()` is called and then `connect()` is called again on the same instance, all previously registered `on()` handlers are lost silently.

🔍 **Impact:**  
The React hook (`useBatchWebSocket`) creates a new instance per connection in `useEffect`, so this is mitigated. But the class API is misleading — it appears reusable but isn't after disconnect.

🏗 **Category:** Architecture / API Design

👉 **Suggested Fix:**  
Either: (a) Don't clear handlers in `_cleanup`, only clear connection state, OR (b) Make the class explicitly single-use and document this.

---

### File: `frontend/src/hooks/useBatchWebSocket.ts`

✅ No issues found — Proper cleanup, buffering with 200ms flush, MAX_LOGS cap, refs for handler stability, disconnect on unmount.

---

### File: `frontend/src/hooks/useBatchProcessing.ts`

**Component/Hook:** `useBatchProcessing`  
**Line:** 91-100  
**Severity:** 🟠 P1

❌ **Issue:**  
The `useEffect` that watches `summary` returns a cleanup function (AbortController abort) but the effect fires on every `summary` change. If `summary` updates rapidly before the batch reaches a terminal status, no abort cleanup runs because the effect doesn't return a cleanup in the non-terminal path. This is correct but the combined state management across two hooks (`useBatchWebSocket` + `useBatchProcessing`) with 8+ useState calls creates cognitive complexity and makes it hard to trace data flow.

🔍 **Impact:**  
Maintainability burden for new developers. The hook exposes 16 return values — a sign of too many responsibilities.

🏗 **Category:** State Management / Architecture

👉 **Refactoring Approach:**  
Extract processing state into a reducer (`useReducer`) or split into two hooks: `useBatchUpload` (upload/parse) and `useBatchExecution` (processing/WS/logs).

---

### File: `frontend/src/components/Layout.tsx`

✅ No issues found

---

### File: `frontend/src/components/layout/NavigationItems.tsx`

**Component/Hook:** `SidebarNav`  
**Line:** 10-95 (navigation array with inline SVG)  
**Severity:** 🟡 P2

❌ **Issue:**  
The `navigation` array is defined at module scope with inline JSX for icons. Each icon is a full SVG element. This makes the array non-serializable and bloats the navigation config with rendering concerns.

🔍 **Impact:**  
Cannot reuse the navigation config for mobile, breadcrumbs, or command palettes without pulling in all SVG markup. Makes adding/removing nav items verbose.

🏗 **Category:** Architecture / Maintainability

👉 **Suggested Fix:**  
Extract icons into a simple icon component or map, and keep the nav config as plain data:

```typescript
const navigation = [
  { name: 'Dashboard', path: '/', icon: 'dashboard' },
  // ...
];
```

---

### File: `frontend/src/components/layout/UserMenu.tsx`

**Component/Hook:** `UserMenu`  
**Line:** 36-47  
**Severity:** 🟡 P2

❌ **Issue:**  
Click-outside detection uses `mousedown` event listener attached/detached on `menuOpen` toggle. This is a correct but repetitive pattern. Every dropdown/popover in the app would need to duplicate this logic.

🔍 **Impact:**  
Code duplication risk as more dropdowns are added. Minor performance concern from repeated add/remove of global listeners.

🏗 **Category:** Code Smell / Reusability

👉 **Suggested Fix:**  
Extract a `useClickOutside(ref, callback)` hook. Many React apps use this pattern:

```typescript
function useClickOutside(ref: RefObject<HTMLElement>, onClose: () => void) {
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [ref, onClose]);
}
```

---

### File: `frontend/src/components/layout/MobileDrawer.tsx`

✅ No issues found — Proper focus trap, accessibility attributes, escape key handling via library.

---

### File: `frontend/src/components/ErrorBoundary.tsx`

✅ No issues found — Proper class component, reset capability, fallback UI.

---

### File: `frontend/src/components/LoadingSpinner.tsx`

✅ No issues found

---

### File: `frontend/src/components/ErrorMessage.tsx`

✅ No issues found

---

### File: `frontend/src/components/SafeHtml.tsx`

✅ No issues found — DOMPurify with strict allowlists, no `style` attribute, no data attributes.

---

### File: `frontend/src/components/StatusBadge.tsx`

✅ No issues found

---

### File: `frontend/src/components/DashboardCharts.tsx`

**Component/Hook:** `DashboardCharts`  
**Line:** 16 (entire component)  
**Severity:** 🟠 P1

❌ **Issue:**  
The component renders 5 heavy Recharts charts (2 PieCharts, 2 LineCharts, 1 BarChart) without memoization. Every time `Dashboard` parent re-renders (e.g., after a refetch), all charts re-render. Recharts components are expensive to reconcile.

🔍 **Impact:**  
Unnecessary re-renders on the most visited page (Dashboard). Each chart calculates layouts, paths, and animations. With 5 charts × expensive render = noticeable jank on lower-end devices.

🏗 **Category:** Rendering Performance

👉 **Suggested Fix:**  
Wrap with `React.memo` since the only prop is `stats`:

```typescript
export default memo(function DashboardCharts({ stats }: DashboardChartsProps) {
  // ...
});
```

---

### File: `frontend/src/components/BatchProcessingView.tsx`

✅ No issues found — Proper `memo` on `CandidateRow` with custom equality check, good performance optimization.

---

### File: `frontend/src/components/BatchUploadSection.tsx`

✅ No issues found — Accessible drop zone with keyboard handler.

---

### File: `frontend/src/components/BatchHistoryTab.tsx`

✅ No issues found

---

### File: `frontend/src/components/LiveExecutionLogs.tsx`

**Component/Hook:** `LiveExecutionLogs`  
**Line:** 44-58  
**Severity:** 🟡 P2

❌ **Issue:**  
Each log entry is rendered without a stable unique key fallback — uses `log.id || idx`. If `id` is undefined and log order changes, React's reconciliation will be incorrect. Additionally, no virtualization is applied to a list that can grow to 500 items.

🔍 **Impact:**  
With 500 log DOM nodes in view, scrolling performance may degrade on mobile. The `max-h-[440px]` overflow scroll partially mitigates this since not all nodes are visible, but they're all in the DOM.

🏗 **Category:** Rendering Performance

👉 **Suggested Fix:**  
For production-grade log viewing with 500+ entries, consider `react-window` or `@tanstack/virtual` for virtualization. For now, ensure all `log.id` values are always defined (they come from the backend, so this should be guaranteed).

---

### File: `frontend/src/components/ProcessingSummary.tsx`

✅ No issues found

---

### File: `frontend/src/components/OCRResultViewer.tsx`

✅ No issues found

---

### File: `frontend/src/components/ClassificationViewer.tsx`

✅ No issues found

---

### File: `frontend/src/components/ValidationResultViewer.tsx`

✅ No issues found

---

### File: `frontend/src/components/ProcessingTimelineView.tsx`

✅ No issues found

---

### File: `frontend/src/components/IntegrationsSection.tsx`

**Component/Hook:** `IntegrationsSection`  
**Line:** 71-78  
**Severity:** 🟡 P2

❌ **Issue:**  
`window.open` for OAuth popup does not validate the `auth_url` received from the API. If the backend is compromised or returns a malicious URL, an open redirect could occur via the popup.

🔍 **Impact:**  
Low severity because the URL comes from your own backend (trusted), but defense-in-depth suggests validating the URL scheme and host before opening.

🏗 **Category:** Security (Defense-in-depth)

👉 **Suggested Fix:**  
```typescript
const url = new URL(auth_url);
if (!['https:', 'http:'].includes(url.protocol) || !url.hostname.endsWith('google.com')) {
  onErrorRef.current('Invalid OAuth URL received');
  setConnecting(false);
  return;
}
```

---

### File: `frontend/src/components/DocumentRulesSection.tsx`

**Component/Hook:** `DocumentRulesSection`  
**Line:** ~160 (`handleDownloadTemplate`)  
**Severity:** 🟡 P2

❌ **Issue:**  
`URL.createObjectURL(blob)` is called but `URL.revokeObjectURL(url)` is never called. The created link element is appended to `document.body` but never removed after click.

🔍 **Impact:**  
Minor memory leak — the blob URL holds a reference until page unload. The orphaned `<a>` element stays in the DOM.

🏗 **Category:** Memory Leak

👉 **Suggested Fix:**  
```typescript
const link = document.createElement('a');
link.href = url;
link.download = 'required-documents-template.csv';
document.body.appendChild(link);
link.click();
document.body.removeChild(link);
URL.revokeObjectURL(url);
```

---

### File: `frontend/src/components/FileNamingSection.tsx`

✅ No issues found

---

### File: `frontend/src/components/ManualUploadForm.tsx`

✅ No issues found

---

### File: `frontend/src/pages/Dashboard.tsx`

**Component/Hook:** `StatCard`  
**Line:** 98-107  
**Severity:** 🟡 P2

❌ **Issue:**  
`StatCard` is defined as a function inside the module but not memoized. Since `STAT_ICON_CONFIG` creates new JSX objects at module load (icon property), the objects are stable. However, `StatCard` itself re-renders on every Dashboard render since it's not wrapped in `memo`.

🔍 **Impact:**  
Low — 4 stat cards are trivial. The real cost is in `DashboardCharts` (addressed above).

🏗 **Category:** Rendering Performance (minor)

👉 **Refactoring Approach:**  
Wrap `StatCard` in `React.memo` if additional stat cards are added in the future.

---

### File: `frontend/src/pages/LoginPage.tsx`

✅ No issues found — Proper redirect for authenticated users, error from URL params, loading state.

---

### File: `frontend/src/pages/AuthCallbackPage.tsx`

**Component/Hook:** `AuthCallbackPage`  
**Line:** 30-34  
**Severity:** 🟡 P2

❌ **Issue:**  
The `callbackLockKey` uses `state` from the URL to create a sessionStorage key: `` `bgv_auth_callback_${state}` ``. While `state` is a CSRF token generated by the backend, storing it in sessionStorage means it persists beyond its single-use purpose. The cleanup happens on success/failure, which is correct, but on page abandonment, the stale entry remains.

🔍 **Impact:**  
Very minor — sessionStorage is tab-scoped and cleared on tab close. No security risk.

🏗 **Category:** Code Smell (minor)

👉 **Suggested Fix:**  
No action needed. The existing cleanup is adequate.

---

### File: `frontend/src/pages/UploadPage.tsx`

**Component/Hook:** `UploadPage`  
**Line:** 37-40  
**Severity:** 🟡 P2

❌ **Issue:**  
`useEffect` with `[tab, loadHistory]` triggers `loadHistory` every time the tab changes to 'history'. The `loadHistory` function is not wrapped in `useCallback` (it's defined in `useBatchProcessing` without memoization), so the eslint-disable comment is needed.

🔍 **Impact:**  
`loadHistory` is a new function reference on every render of `useBatchProcessing`, which is why the eslint rule is suppressed. This means the effect technically runs on every render when `tab === 'history'`, but since `loadHistory` sets loading state and the data is idempotent, the user doesn't notice.

🏗 **Category:** Hooks / Architecture

👉 **Suggested Fix:**  
Wrap `loadHistory` in `useCallback` inside `useBatchProcessing`:

```typescript
const loadHistory = useCallback(async () => {
  // ...
}, []);
```

---

### File: `frontend/src/pages/BatchHistoryPage.tsx`

**Component/Hook:** `BatchHistoryPage`  
**Line:** 36-39  
**Severity:** 🟡 P2

❌ **Issue:**  
`handleSearch` sets page to 0 and relies on the `useEffect` to re-fetch. But the comment says "loadData triggers automatically via useEffect when page/filters change." The `searchQuery` is applied client-side (via `filteredBatches` memo) and is NOT sent to the API. This means only the locally-loaded page of 25 results is searched — not the full dataset.

🔍 **Impact:**  
Users may think they're searching all batches but are only filtering the current page of 25. This is a UX bug, not a security issue.

🏗 **Category:** Architecture / UX

👉 **Suggested Fix:**  
Either: (a) Send `searchQuery` as a parameter to the API for server-side filtering, OR (b) Clearly label the search as "Filter visible results" to set user expectations.

---

### File: `frontend/src/pages/BatchDetailPage.tsx`

✅ No issues found — Proper loading/error/empty states, expand/collapse, progress calculation.

---

### File: `frontend/src/pages/DocumentDetailPage.tsx`

**Component/Hook:** `DocumentDetailPage`  
**Line:** 64-76  
**Severity:** 🟡 P2

❌ **Issue:**  
Auto-polling with `setInterval(poll, 5000)` while the document is processing. The `poll` function calls `loadDataRef.current?.(false)` which fetches 3 API endpoints in parallel (`getDocumentDetail`, `getProcessingTimeline`, `checkHealth`). Calling `checkHealth` every 5 seconds during polling is wasteful — health status doesn't change that frequently.

🔍 **Impact:**  
Unnecessary API load. 3 requests every 5s per open document detail page. `checkHealth` only needs to be fetched once.

🏗 **Category:** API Optimization / Performance

👉 **Suggested Fix:**  
Fetch `checkHealth` only on initial load (not during polling). Create a separate `refreshDocument` function that only calls `getDocumentDetail` and `getProcessingTimeline`:

```typescript
const refreshData = useCallback(async () => {
  if (!documentId) return;
  const [docDetail, timelineData] = await Promise.allSettled([
    getDocumentDetail(documentId),
    getProcessingTimeline(documentId),
  ]);
  if (docDetail.status === 'fulfilled') setDetail(docDetail.value);
  if (timelineData.status === 'fulfilled') setTimeline(timelineData.value);
}, [documentId]);
```

---

### File: `frontend/src/pages/CandidatesPage.tsx`

✅ No issues found — Proper pagination, loading states.

---

### File: `frontend/src/pages/AuditPage.tsx`

**Component/Hook:** `AuditPage`  
**Line:** 8-10  
**Severity:** 🟡 P2

❌ **Issue:**  
`const today = new Date().toISOString().split('T')[0];` is computed on EVERY render because it's inside the component body but outside `useState` initializer. This means `dateFrom` and `dateTo` default values use the first render's date (via `useState(today)`) but `today` is recomputed each render (wasted computation).

🔍 **Impact:**  
Negligible performance impact but indicates the variable should be moved to a constant or computed once.

🏗 **Category:** Code Smell (minor)

👉 **Suggested Fix:**  
Use a lazy initializer or extract to module scope:
```typescript
const getToday = () => new Date().toISOString().split('T')[0];
// Inside component:
const [dateFrom, setDateFrom] = useState(getToday);
```

---

### File: `frontend/src/pages/ReviewQueuePage.tsx`

✅ No issues found — Proper bulk selection, notification handling, pagination, search.

---

### File: `frontend/src/pages/ProfilePage.tsx`

✅ No issues found

---

### File: `frontend/src/pages/DocumentsPage.tsx`

✅ No issues found (from reviewed portion)

---

### File: `frontend/src/types/index.ts`

✅ No issues found — Well-structured, complete type definitions.

---

### File: `frontend/src/types/auth.ts`

✅ No issues found

---

### File: `frontend/src/index.css`

✅ No issues found — Proper Tailwind layer usage, component classes, utility animations.

---

## 2. 🔁 Duplication Report

| # | Type | Location A | Location B | Impact |
|---|------|-----------|-----------|--------|
| 1 | **Type Definition** | `api/endpoints.ts` → `BatchLogItem` (L156-166) | `types/index.ts` → `BatchLogEntry` (L247-258) | Two near-identical interfaces for the same data shape |
| 2 | **Status Styling** | `utils/formatting.ts` → `statusColor()` | `components/StatusBadge.tsx` → `statusConfig` | Two separate status-to-CSS mappings for the same concept |
| 3 | **Status Badge Logic** | `pages/ReviewQueuePage.tsx` → `statusBadge()` helper | `utils/formatting.ts` → `statusColor()` | Third instance of status-to-class mapping |
| 4 | **Click-outside Pattern** | `components/layout/UserMenu.tsx` (L36-47) | Pattern will repeat for any future dropdown | No shared hook exists |
| 5 | **Date formatting** | Inline `new Date(x).toLocaleDateString()` used in 6+ files | — | No centralized date formatter utility |
| 6 | **File size formatting** | `pages/DocumentDetailPage.tsx` → `formatFileSize()` | — | Only one instance currently, but candidate for shared utility |

---

## 3. 🚨 Critical Tech Debt (P0)

**No P0 (Critical) issues found.**

Security posture is strong:
- ✅ Session tokens are httpOnly cookies (not accessible via JS)
- ✅ No token in localStorage/sessionStorage
- ✅ HTML rendering uses DOMPurify with strict allowlists (`SafeHtml.tsx`)
- ✅ OAuth callback sanitizes error params (`safeError` strips `<>"'`)
- ✅ No `dangerouslySetInnerHTML` without sanitization
- ✅ No XSS vectors in user-facing inputs
- ✅ CSRF protection via httpOnly cookie + SameSite (server-side)
- ✅ WebSocket auth uses single-use ticket pattern (not raw session token)
- ✅ No sensitive data exposed in client-side code
- ✅ No infinite render loops detected
- ✅ No memory leaks causing crashes (only minor blob URL leak)

---

## 4. ⚠️ High & Medium Debt

### 🟠 P1 (High Priority)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `components/DashboardCharts.tsx` | 5 expensive Recharts components without `React.memo` | Unnecessary re-renders on most-visited page |
| 2 | `hooks/useBatchProcessing.ts` | 8 useState + 16 return values, complex cross-hook state | High cognitive complexity, hard to maintain |

### 🟡 P2 (Medium Priority)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `api/endpoints.ts` | `BatchLogItem` duplicates `BatchLogEntry` type | Type confusion |
| 2 | `utils/formatting.ts` | `statusColor` duplicates `StatusBadge` logic | Maintenance burden |
| 3 | `services/websocket.ts` | `_cleanup()` clears handlers making instance non-reusable | API misleading |
| 4 | `components/LiveExecutionLogs.tsx` | 500 DOM nodes without virtualization | Mobile scroll jank |
| 5 | `components/IntegrationsSection.tsx` | OAuth popup URL not validated | Defense-in-depth gap |
| 6 | `components/DocumentRulesSection.tsx` | Blob URL + DOM element leak in download | Minor memory leak |
| 7 | `pages/DocumentDetailPage.tsx` | `checkHealth` called every 5s during polling | Wasted API calls |
| 8 | `pages/BatchHistoryPage.tsx` | Client-side search on 25-item page misleads users | UX issue |
| 9 | `pages/UploadPage.tsx` | `loadHistory` not memoized in source hook | Effect runs too often |
| 10 | `layout/NavigationItems.tsx` | Inline SVG in navigation config array | Non-serializable config |
| 11 | `api/client.ts` | Module-level `isHandling401` semaphore is fragile | Future refactor risk |
| 12 | `pages/AuditPage.tsx` | `today` computed on every render | Minor waste |

---

## 5. 💡 Strategic Improvements

### Component Architecture
- **Extract shared UI primitives**: `useClickOutside` hook, `StatusBadge` consolidated with `statusColor`, shared `DateDisplay` component.
- **Icon System**: Replace inline SVGs with an icon component/map for consistency and tree-shaking.

### State Management
- **Decompose `useBatchProcessing`**: Split into `useBatchUpload` (file handling, parsing) and `useBatchExecution` (WebSocket, processing state, logs).
- **Consider `useReducer`**: For the batch processing state machine (pending → uploading → parsed → processing → complete/failed).

### Code Splitting
- ✅ Already implemented (lazy routes, lazy DashboardCharts). Good.
- **Future**: Lazy-load `IntegrationsSection`, `DocumentRulesSection`, `FileNamingSection` within SettingsPage if bundle grows.

### Lazy Loading
- ✅ All route-level pages are lazy-loaded. Well done.
- **Recharts** is the largest dependency — already lazy-loaded via `DashboardCharts`. Good.

### Accessibility
- ✅ Focus trap on mobile drawer
- ✅ `aria-label`, `aria-hidden`, `aria-modal` used correctly
- ✅ Keyboard navigation on upload dropzone
- **Gap**: Tables lack `<caption>` elements for screen readers.
- **Gap**: No skip-to-main-content link.
- **Gap**: Color-only status indicators (badges) — should have text/icon for colorblind users (already has text, so OK).

### Design System
- ✅ Consistent Tailwind component classes (`.btn-primary`, `.card`, `.input-field`, `.badge-*`).
- **Improvement**: Extract repeated `text-[10px] font-bold uppercase tracking-widest text-gray-400` micro-label pattern into a component class.

### Error Handling
- ✅ Error boundaries at app level
- ✅ Per-page error states with retry
- ✅ API interceptor for 401
- **Improvement**: Consider a toast/notification system instead of inline error divs on pages like ReviewQueuePage (already has toast — good) and SettingsPage.

### Frontend Observability
- **Add**: Error reporting service integration (Sentry/Datadog RUM) in ErrorBoundary's `componentDidCatch`.
- **Add**: Performance monitoring for Core Web Vitals.
- **Currently**: Only `console.error` in ErrorBoundary and `console.warn` in WebSocket (dev-only).

---

## 6. 📊 Frontend Quality Scorecard

| Category | Score |
|----------|-------|
| Naming | 90/100 |
| Component Design | 88/100 |
| Hooks Usage | 85/100 |
| Performance | 82/100 |
| API Handling | 87/100 |
| Security | 95/100 |
| Accessibility | 80/100 |
| DRY | 78/100 |
| Maintainability | 83/100 |
| State Management | 79/100 |
| Scalability | 82/100 |

**Frontend Score: 84/100**

---

## 7. 📉 Frontend Tech Debt Summary

| Metric | Count |
|--------|-------|
| **Total Issues** | 14 |
| 🔴 **P0 (Critical)** | 0 |
| 🟠 **P1 (High)** | 2 |
| 🟡 **P2 (Medium)** | 12 |
| **Duplication Cases** | 6 |

**Frontend Tech Debt Level: 🟡 Medium**

The codebase has no critical security vulnerabilities, no infinite loops, no memory crashes, and follows modern React patterns. The debt is primarily in maintainability (duplication, state complexity) and minor performance optimizations.

---

## 8. 🧾 Final Verdict

### ⚠️ Needs Improvement (Production-Worthy with caveats)

**Justification:**

| Dimension | Assessment |
|-----------|------------|
| **Security Posture** | ✅ Excellent — httpOnly cookies, DOMPurify, no token exposure, ticket-based WS auth |
| **Rendering Performance** | ⚠️ Good with gaps — DashboardCharts needs memo, LiveExecutionLogs could use virtualization |
| **Scalability** | ⚠️ Good — Lazy loading in place, but `useBatchProcessing` hook complexity will be a bottleneck as features grow |
| **Maintainability** | ⚠️ Moderate — Status duplication, coupled state hooks, inline SVGs increase onboarding cost |
| **UX Reliability** | ✅ Good — Proper loading/error/empty states across all pages, error boundaries, graceful WebSocket reconnection |

**Summary:** This is a well-architected React application with strong security practices and good code splitting. The primary tech debt is moderate-severity maintainability issues (duplication, state complexity) that should be addressed before the next major feature sprint to avoid accumulation. No blockers for production deployment.
