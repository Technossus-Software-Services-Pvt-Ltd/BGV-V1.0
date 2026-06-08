# Frontend Tech Debt Audit Report v6

**Date:** June 5, 2026  
**Auditors:** Principal Frontend Architect, Senior React Architect, UI Performance Engineer, Staff Security Engineer, Enterprise Solution Architect  
**Scope:** Full codebase review — `frontend/src/**`  
**Stack:** React 18, TypeScript (strict), Vite 5, Tailwind CSS 3, Axios, React Router 6, Recharts, DOMPurify

---

## 1. 📁 File-Level Tech Debt

---

### File: `frontend/src/pages/DocumentDetailPage.tsx`

**Component/Hook:** `DocumentDetailPage`  
**Line:** 3–4  
**Severity:** 🔴 P0 (Critical)

❌ **Issue:**  
Duplicate import of `useParams` (imported from both `react-router-dom` on line 3 and again on line 4). This is a **compilation error** that will fail the TypeScript build.

```tsx
import { useParams } from 'react-router-dom';
import { useParams, Link } from 'react-router-dom';
```

🔍 **Impact:**  
Build failure — the application cannot compile. This is a production blocker.

🏗 **Category:** Architecture / Build

👉 **Suggested Fix:**
```tsx
import { useParams, Link } from 'react-router-dom';
```

---

### File: `frontend/src/pages/DocumentDetailPage.tsx`

**Component/Hook:** `DocumentDetailPage`  
**Line:** 3  
**Severity:** 🟠 P1 (High)

❌ **Issue:**  
`checkHealth` is imported with a missing space after the comma: `getProcessingTimeline,checkHealth` — while cosmetic, the dual `useParams` import above makes this file broken.

🔍 **Impact:**  
Code quality / linting failure.

🏗 **Category:** Code Smell

👉 **Suggested Fix:**
```tsx
import { getDocumentDetail, getProcessingTimeline, checkHealth } from '../api/endpoints';
```

---

### File: `frontend/src/pages/DocumentDetailPage.tsx`

**Component/Hook:** `DocumentDetailPage`  
**Line:** ~200  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
`formatFileSize` utility function is duplicated — defined locally in this file AND identically in `BatchDetailPage.tsx`. This violates DRY.

🔍 **Impact:**  
Maintainability — bug fixes must be applied in multiple places.

🏗 **Category:** Duplication / Code Smell

👉 **Suggested Fix:**  
Extract `formatFileSize` to `src/utils/formatting.ts` and import from there.

---

### File: `frontend/src/pages/BatchDetailPage.tsx`

**Component/Hook:** `formatFileSize`  
**Line:** ~370  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
Duplicate implementation of `formatFileSize`. Same function also in `DocumentDetailPage.tsx`.

🔍 **Impact:**  
DRY violation, maintenance burden.

🏗 **Category:** Duplication

👉 **Suggested Fix:**
```tsx
// src/utils/formatting.ts
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
```

---

### File: `frontend/src/pages/AuditPage.tsx`

**Component/Hook:** `AuditPage`  
**Line:** ~170  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
`statusColor` function is redefined locally inside `BatchListView` subcomponent while the same logic already exists in `src/utils/formatting.ts`.

🔍 **Impact:**  
Duplication — same logic in two places.

🏗 **Category:** Duplication

👉 **Suggested Fix:**  
Import `statusColor` from `../utils/formatting`.

---

### File: `frontend/src/pages/UploadPage.tsx`

**Component/Hook:** `UploadPage`  
**Line:** 37 (`useEffect`)  
**Severity:** 🟠 P1 (High)

❌ **Issue:**  
`useEffect` with dependency `[tab]` calls `loadHistory()` but `loadHistory` is not in the dependency array. This triggers the `react-hooks/exhaustive-deps` rule violation. More critically, `loadHistory` is a **non-memoized** function from `useBatchProcessing`, meaning each render creates a new reference — if added to deps it would cause an infinite loop.

```tsx
useEffect(() => {
  if (tab === 'history') {
    loadHistory();
  }
}, [tab]);
```

🔍 **Impact:**  
Stale closure risk — `loadHistory` may reference stale state. Also, ESLint exhaustive-deps warning.

🏗 **Category:** Hooks

👉 **Suggested Fix:**  
Wrap `loadHistory` inside `useBatchProcessing` with `useCallback` (it already closes over no changing deps), then add it to the dependency array:
```tsx
// In useBatchProcessing.ts
const loadHistory = useCallback(async () => { ... }, []);
```

---

### File: `frontend/src/hooks/useBatchProcessing.ts`

**Component/Hook:** `useBatchProcessing`  
**Line:** entire hook  
**Severity:** 🟠 P1 (High)

❌ **Issue:**  
This hook manages **7 distinct state values** and returns **14 items**. It conflates upload state, processing state, history state, WebSocket state, and error state into a single monolithic hook. Any consumer re-renders on ANY state change.

🔍 **Impact:**  
Performance — the entire `UploadPage` and all child components re-render when any piece of batch state changes (e.g., every WebSocket log entry causes a full tree re-render).

🏗 **Category:** State / Architecture / Performance

👉 **Refactoring Approach:**  
Split into focused hooks:
- `useBatchUpload` — handles file upload + parse
- `useBatchExecution` — handles start processing + websocket state
- `useBatchHistory` — handles history listing

---

### File: `frontend/src/hooks/useBatchWebSocket.ts`

**Component/Hook:** `useBatchWebSocket`  
**Line:** 108 (useEffect dependency array)  
**Severity:** 🟠 P1 (High)

❌ **Issue:**  
The `useEffect` that manages WebSocket lifecycle includes `handleLog`, `handleCandidateStatus`, and `handleSummary` in its dependency array. Although these are wrapped in `useCallback`, if any parent re-renders with different prop-derived values, the WebSocket will disconnect and reconnect unnecessarily (full teardown + reconnect cycle).

🔍 **Impact:**  
Potential WebSocket disconnection during active batch processing, causing missed updates.

🏗 **Category:** Hooks / Performance

👉 **Suggested Fix:**  
Use refs for the handlers instead of putting them in the dep array:
```tsx
const handleLogRef = useRef(handleLog);
handleLogRef.current = handleLog;
// In effect: ws.on('processing-log', (data) => handleLogRef.current(data));
```
Only `batchId` should be in the dependency array.

---

### File: `frontend/src/pages/DocumentsPage.tsx`

**Component/Hook:** `DocumentsPage`  
**Line:** ~64-72 (polling effect)  
**Severity:** 🟠 P1 (High)

❌ **Issue:**  
Aggressive polling every 5 seconds with `setInterval` regardless of visibility state. When tab is backgrounded or minimized, polling continues, flooding the backend with requests.

🔍 **Impact:**  
API flooding — unnecessary network requests when user is not viewing the page. Increases backend load.

🏗 **Category:** Performance / API Handling

👉 **Suggested Fix:**  
Add `document.visibilityState` check (as done in `DocumentDetailPage.tsx`) and pause polling when tab is hidden:
```tsx
useEffect(() => {
  if (!hasProcessingDocs) return;
  const poll = () => {
    if (document.visibilityState === 'visible') loadDataRef.current?.(false);
  };
  const id = setInterval(poll, 5000);
  const onVisibility = () => { if (document.visibilityState === 'visible') poll(); };
  document.addEventListener('visibilitychange', onVisibility);
  return () => { clearInterval(id); document.removeEventListener('visibilitychange', onVisibility); };
}, [hasProcessingDocs]);
```

---

### File: `frontend/src/pages/BatchDetailPage.tsx`

**Component/Hook:** `BatchDetailPage`  
**Line:** 34–50  
**Severity:** 🟠 P1 (High)

❌ **Issue:**  
Fetches documents for ALL candidates in parallel, chunked by 5. For large batches (e.g., 200 candidates), this creates 40 sequential chunk requests. Additionally, documents are fetched with `limit: 100` per candidate, potentially pulling thousands of records into browser memory.

🔍 **Impact:**  
Performance — extremely slow page load for large batches. Memory pressure. API load.

🏗 **Category:** Performance / API Handling

👉 **Suggested Fix:**  
1. Add a batch-level API endpoint that returns all documents for a batch in one call.
2. If not possible, implement virtual scrolling and on-demand loading per candidate (only fetch when expanded).

---

### File: `frontend/src/components/layout/MobileDrawer.tsx`

**Component/Hook:** `MobileDrawer`  
**Line:** entire component  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
No focus trap implementation. The comment says "Trap focus inside drawer when open" but only Escape key handling is implemented. A keyboard user can Tab outside the drawer while it's visually open.

🔍 **Impact:**  
Accessibility (A11y) — violates WCAG 2.1 SC 2.4.3 (Focus Order) for modal dialogs.

🏗 **Category:** Accessibility

👉 **Suggested Fix:**  
Use the already-installed `focus-trap-react` package:
```tsx
import FocusTrap from 'focus-trap-react';

// Wrap the aside content:
<FocusTrap active={open}>
  <aside ...>...</aside>
</FocusTrap>
```

---

### File: `frontend/src/components/layout/UserMenu.tsx`

**Component/Hook:** `UserMenu`  
**Line:** 96 (sidebar popup)  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
Dropdown menu lacks ARIA attributes (`role="menu"`, `role="menuitem"`, `aria-expanded`). Keyboard navigation (arrow keys) is not implemented.

🔍 **Impact:**  
Accessibility — screen readers cannot navigate the menu properly.

🏗 **Category:** Accessibility

👉 **Suggested Fix:**
```tsx
<button aria-expanded={menuOpen} aria-haspopup="true" ...>
<div role="menu" ...>
  <button role="menuitem" ...>Profile</button>
  <button role="menuitem" ...>Logout</button>
</div>
```

---

### File: `frontend/src/pages/ReviewQueuePage.tsx`

**Component/Hook:** `ReviewQueuePage`  
**Line:** ~125 (handleBulkNotify)  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
No confirmation dialog before bulk email sending. A misclick on the "Notify Selected" button immediately sends emails to all selected candidates.

🔍 **Impact:**  
UX reliability — accidental mass notifications cannot be undone.

🏗 **Category:** Architecture / UX

👉 **Suggested Fix:**  
Add a confirmation modal: "Send notification to X candidates? This cannot be undone."

---

### File: `frontend/src/pages/Dashboard.tsx`

**Component/Hook:** `Dashboard`  
**Line:** 76-130 (PieChart render)  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
Charts re-render entirely on every parent state change because the `label` function prop creates a new reference on every render:
```tsx
label={({ name, value }) => `${name ?? ''}: ${value ?? ''}`}
```

🔍 **Impact:**  
Minor rendering inefficiency — each Recharts re-render is expensive due to SVG diffing.

🏗 **Category:** Rendering / Performance

👉 **Suggested Fix:**  
Extract label function outside the component or memoize:
```tsx
const pieLabel = useCallback(({ name, value }) => `${name ?? ''}: ${value ?? ''}`, []);
```

---

### File: `frontend/src/components/SafeHtml.tsx`

**Component/Hook:** `SafeHtml`  
**Line:** 13  
**Severity:** ✅ No issues found

Well-implemented. Uses DOMPurify with explicit allowlists and forbids `style` attributes. Secure against XSS.

---

### File: `frontend/src/components/ErrorBoundary.tsx`

✅ No issues found. Properly implemented class-based error boundary with reset capability.

---

### File: `frontend/src/components/LoadingSpinner.tsx`

✅ No issues found.

---

### File: `frontend/src/components/ErrorMessage.tsx`

✅ No issues found.

---

### File: `frontend/src/components/StatusBadge.tsx`

✅ No issues found.

---

### File: `frontend/src/components/ProcessingSummary.tsx`

✅ No issues found.

---

### File: `frontend/src/components/LiveExecutionLogs.tsx`

✅ No issues found. Smart auto-scroll with bottom detection.

---

### File: `frontend/src/components/OCRResultViewer.tsx`

✅ No issues found.

---

### File: `frontend/src/components/ClassificationViewer.tsx`

✅ No issues found.

---

### File: `frontend/src/components/ValidationResultViewer.tsx`

**Component/Hook:** `OpenAIResultSection`  
**Line:** ~72  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
`JSON.parse` of `openai_key_evidence_json` and `openai_concerns_json` is called without try/catch. If the backend returns malformed JSON, this will throw and potentially crash the component (unless caught by ErrorBoundary).

🔍 **Impact:**  
Runtime crash risk — could render blank screen for that component.

🏗 **Category:** Error Handling

👉 **Suggested Fix:**
```tsx
const keyEvidence: string[] = (() => {
  try { return result.openai_key_evidence_json ? JSON.parse(result.openai_key_evidence_json) : []; }
  catch { return []; }
})();
```

---

### File: `frontend/src/components/ProcessingTimelineView.tsx`

✅ No issues found.

---

### File: `frontend/src/components/BatchUploadSection.tsx`

✅ No issues found.

---

### File: `frontend/src/components/BatchHistoryTab.tsx`

✅ No issues found.

---

### File: `frontend/src/components/BatchProcessingView.tsx`

✅ No issues found.

---

### File: `frontend/src/components/ManualUploadForm.tsx`

✅ No issues found.

---

### File: `frontend/src/components/IntegrationsSection.tsx`

✅ No issues found.

---

### File: `frontend/src/components/DocumentRulesSection.tsx`

✅ No issues found.

---

### File: `frontend/src/components/FileNamingSection.tsx`

✅ No issues found.

---

### File: `frontend/src/components/Layout.tsx`

✅ No issues found. Clean layout with responsive sidebar.

---

### File: `frontend/src/components/layout/NavigationItems.tsx`

✅ No issues found.

---

### File: `frontend/src/components/layout/index.ts`

✅ No issues found.

---

### File: `frontend/src/App.tsx`

✅ No issues found. Proper lazy loading, Suspense boundaries, route guards, Error Boundary wrapper.

---

### File: `frontend/src/main.tsx`

✅ No issues found. Proper StrictMode, BrowserRouter, AuthProvider wrapping.

---

### File: `frontend/src/api/client.ts`

✅ No issues found. Good 401 handling with debounce, session cookie approach.

---

### File: `frontend/src/api/endpoints.ts`

✅ No issues found. Well-typed, consistent patterns.

---

### File: `frontend/src/services/websocket.ts`

✅ No issues found. Excellent implementation with ticket-based auth, exponential backoff, heartbeat, and proper cleanup.

---

### File: `frontend/src/hooks/useAuth.tsx`

✅ No issues found. Clean context pattern with cross-tab sync via StorageEvent.

---

### File: `frontend/src/utils/auth.ts`

✅ No issues found. HttpOnly cookie design is correct — localStorage stores only non-sensitive profile data.

---

### File: `frontend/src/utils/formatting.ts`

✅ No issues found (though more utilities should be consolidated here).

---

### File: `frontend/src/types/index.ts`

✅ No issues found. Comprehensive, well-typed interfaces.

---

### File: `frontend/src/types/auth.ts`

✅ No issues found.

---

### File: `frontend/src/index.css`

✅ No issues found. Clean Tailwind layer usage with custom utilities.

---

### File: `frontend/vite.config.ts`

✅ No issues found.

---

### File: `frontend/tsconfig.json`

✅ No issues found. Strict mode enabled with proper path aliases.

---

### File: `frontend/tailwind.config.js`

✅ No issues found.

---

### File: `frontend/package.json`

**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
`@types/dompurify` is listed under `dependencies` instead of `devDependencies`. Type packages should never ship to production.

🔍 **Impact:**  
Slightly larger install footprint. Poor package hygiene.

🏗 **Category:** Build Configuration

👉 **Suggested Fix:**  
Move `@types/dompurify` to `devDependencies`.

---

### File: `frontend/src/pages/ProfilePage.tsx`

✅ No issues found.

---

### File: `frontend/src/pages/LoginPage.tsx`

✅ No issues found. Proper redirect loop prevention.

---

### File: `frontend/src/pages/AuthCallbackPage.tsx`

✅ No issues found. Good double-submit prevention with `hasRun` ref and `callbackLockKey`.

---

### File: `frontend/src/pages/CandidatesPage.tsx`

**Component/Hook:** `CandidatesPage`  
**Line:** entire component  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
No pagination UI. The component fetches `limit: 100` candidates but displays `total` in the header. Users with >100 candidates cannot access remaining records.

🔍 **Impact:**  
Feature gap — data truncation without user awareness.

🏗 **Category:** Architecture / UX

👉 **Suggested Fix:**  
Add pagination controls (next/prev) similar to `ReviewQueuePage`.

---

### File: `frontend/src/pages/SettingsPage.tsx`

✅ No issues found. Clean scroll-spy sidebar implementation.

---

### File: `frontend/src/pages/BatchHistoryPage.tsx`

**Component/Hook:** `BatchHistoryPage`  
**Line:** 23 (loadData)  
**Severity:** 🟡 P2 (Medium)

❌ **Issue:**  
Fetches up to `limit: 200` batches without pagination. For growing datasets, this will degrade.

🔍 **Impact:**  
Scalability — response payload and render time grow linearly.

🏗 **Category:** Scalability

👉 **Suggested Fix:**  
Add server-side pagination with skip/limit controls in the UI.

---

### File: `frontend/src/vite-env.d.ts`

✅ No issues found (standard Vite type reference).

---

## 2. 🔁 Duplication Report

| Duplicate | Locations | Fix |
|-----------|-----------|-----|
| `formatFileSize()` | `DocumentDetailPage.tsx`, `BatchDetailPage.tsx` | Move to `utils/formatting.ts` |
| `statusColor()` local re-implementation | `AuditPage.tsx` (inline) | Import from `utils/formatting.ts` |
| File upload drop-zone pattern | `BatchUploadSection.tsx`, `ManualUploadForm.tsx` | Extract reusable `DropZone` component |
| Inline SVG icons (identical patterns) | Multiple components (~7 files) | Extract to an `Icons.tsx` barrel |
| Status badge class logic | `ReviewQueuePage.tsx` (local `statusBadge` fn) vs `StatusBadge` component | Reuse `StatusBadge` component |

**Total Duplication Cases: 5**

---

## 3. 🚨 Critical Tech Debt (P0)

| # | Issue | File | Impact |
|---|-------|------|--------|
| 1 | Duplicate `useParams` import — build failure | `DocumentDetailPage.tsx:3-4` | App cannot compile |

**No XSS vulnerabilities found** — DOMPurify is properly configured. Session tokens use httpOnly cookies. No tokens stored in localStorage. WebSocket uses ticket-based auth. No `eval()` or unsafe patterns detected.

---

## 4. ⚠️ High & Medium Debt

### 🟠 P1 (High)

| # | Issue | File | Category |
|---|-------|------|----------|
| 1 | Monolithic `useBatchProcessing` hook — excessive re-renders | `useBatchProcessing.ts` | State/Performance |
| 2 | WebSocket effect handler deps cause reconnections | `useBatchWebSocket.ts:108` | Hooks/Performance |
| 3 | Missing `loadHistory` in useEffect deps | `UploadPage.tsx:37` | Hooks |
| 4 | Polling without visibility check | `DocumentsPage.tsx:64` | Performance/API |
| 5 | N+1 document loading pattern (per-candidate) | `BatchDetailPage.tsx:34` | Performance/API |

### 🟡 P2 (Medium)

| # | Issue | File | Category |
|---|-------|------|----------|
| 1 | `formatFileSize` duplicated | 2 files | DRY |
| 2 | `statusColor` duplicated | AuditPage | DRY |
| 3 | No focus trap on MobileDrawer | `MobileDrawer.tsx` | Accessibility |
| 4 | UserMenu missing ARIA attrs | `UserMenu.tsx` | Accessibility |
| 5 | No confirm dialog for bulk notify | `ReviewQueuePage.tsx` | UX |
| 6 | Chart inline functions cause re-renders | `Dashboard.tsx` | Performance |
| 7 | JSON.parse without try/catch | `ValidationResultViewer.tsx` | Error Handling |
| 8 | `@types/dompurify` in prod deps | `package.json` | Build Config |
| 9 | CandidatesPage missing pagination | `CandidatesPage.tsx` | Scalability |
| 10 | BatchHistoryPage fetches 200 without pagination | `BatchHistoryPage.tsx` | Scalability |

---

## 5. 💡 Strategic Improvements

### Component Architecture Redesign
- Extract a reusable `<DropZone>` component for all file upload areas.
- Extract inline SVG icons into a shared `Icons.tsx` component library.
- Create a `<ConfirmDialog>` component for destructive actions.

### State Management Improvements
- Split `useBatchProcessing` into 3 focused hooks to reduce re-render scope.
- Use `useReducer` for complex batch state transitions instead of multiple `useState` calls.
- Consider React Query / TanStack Query for server-state management (caching, polling, deduplication).

### Code Splitting Strategies
- Already well-implemented via `lazy()` for page-level splitting. ✅
- Consider splitting large `recharts` import via dynamic import for Dashboard only (already page-split).

### Lazy Loading Improvements
- Page-level lazy loading is correctly implemented. ✅
- Consider preloading adjacent routes on hover (e.g., `BatchDetailPage` when hovering a batch row).

### Accessibility Improvements
- Implement focus trap on `MobileDrawer` using installed `focus-trap-react`.
- Add `aria-expanded`, `role="menu"`, `role="menuitem"` to `UserMenu`.
- Add `aria-live="polite"` to toast notifications in `ReviewQueuePage`.
- Ensure all interactive SVG icons have accessible labels (some already have `aria-hidden="true"` — good).

### Design System Standardization
- The Tailwind component layer in `index.css` (`.btn-primary`, `.card`, `.badge-*`, `.input-field`) is a solid foundation. 
- Consolidate badge rendering — eliminate inline `statusBadge` functions and always use the `<StatusBadge>` component.

### Error Handling Strategy
- Wrap `JSON.parse` calls in try/catch throughout the app.
- Add error boundary at page-level (currently only at App root level) for more granular recovery.

### Frontend Observability Improvements
- Add error reporting integration (e.g., Sentry) — currently only `console.error` in ErrorBoundary.
- Track WebSocket disconnect/reconnect events in telemetry.
- Monitor long-running API calls with performance markers.

---

## 6. 📊 Frontend Quality Scorecard

| Category | Score |
|----------|-------|
| Naming | 92/100 |
| Component Design | 85/100 |
| Hooks Usage | 78/100 |
| Performance | 74/100 |
| API Handling | 82/100 |
| Security | 95/100 |
| Accessibility | 68/100 |
| DRY | 80/100 |
| Maintainability | 83/100 |
| State Management | 72/100 |
| Scalability | 70/100 |

**Frontend Score: 80/100**

---

## 7. 📉 Frontend Tech Debt Summary

| Metric | Count |
|--------|-------|
| **Total Issues** | 16 |
| 🔴 P0 (Critical) | 1 |
| 🟠 P1 (High) | 5 |
| 🟡 P2 (Medium) | 10 |
| **Duplication Cases** | 5 |

**Frontend Tech Debt Level: 🟡 Medium**

---

## 8. 🧾 Final Verdict

### ⚠️ Needs Improvement

**Justification:**

| Area | Assessment |
|------|-----------|
| **Security Posture** | ✅ Excellent — httpOnly cookies, DOMPurify for HTML rendering, ticket-based WebSocket auth, no token exposure in localStorage, proper CORS with `withCredentials`. No XSS vectors found. |
| **Rendering Performance** | ⚠️ Moderate — monolithic `useBatchProcessing` hook causes full-tree re-renders during active processing. WebSocket handler deps may cause unnecessary reconnections. Polling without visibility check on `DocumentsPage`. |
| **Scalability** | ⚠️ Moderate — N+1 API pattern in `BatchDetailPage`, missing pagination in `CandidatesPage` and `BatchHistoryPage`, 200-record fetches without lazy loading. |
| **Maintainability** | ✅ Good — clean TypeScript types, consistent patterns, proper separation of concerns. Some duplication exists but is manageable. |
| **UX Reliability** | ⚠️ Moderate — `DocumentDetailPage.tsx` has a build-blocking duplicate import (P0). Missing focus traps and ARIA attrs reduce accessibility. No confirmation for bulk operations. |

**Resolution Priority:**
1. **Immediate:** Fix the duplicate `useParams` import in `DocumentDetailPage.tsx` (P0 — blocks builds).
2. **Sprint 1:** Split `useBatchProcessing` hook, add visibility-aware polling, fix WebSocket effect deps.
3. **Sprint 2:** Add pagination, focus traps, ARIA attributes, consolidate duplicate utilities.
