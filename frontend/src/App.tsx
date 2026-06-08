import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import LoadingSpinner from './components/LoadingSpinner';
import LoginPage from './pages/LoginPage';
import AuthCallbackPage from './pages/AuthCallbackPage';
import { useAuth } from './hooks/useAuth';

// Lazy-loaded pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'));
const UploadPage = lazy(() => import('./pages/UploadPage'));
const BatchHistoryPage = lazy(() => import('./pages/BatchHistoryPage'));
const BatchDetailPage = lazy(() => import('./pages/BatchDetailPage'));
const DocumentDetailPage = lazy(() => import('./pages/DocumentDetailPage'));
const CandidatesPage = lazy(() => import('./pages/CandidatesPage'));
const AuditPage = lazy(() => import('./pages/AuditPage'));
const ReviewQueuePage = lazy(() => import('./pages/ReviewQueuePage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));

function PageSuspense({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingSpinner message="Loading..." />}>{children}</Suspense>;
}

function ProtectedLayout() {
  const { isLoggedIn } = useAuth();
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }
  return <Layout />;
}

function LoginRoute() {
  const { isLoggedIn } = useAuth();
  if (isLoggedIn) {
    return <Navigate to="/" replace />;
  }
  return <LoginPage />;
}

function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginRoute />} />
        <Route path="/auth/callback" element={<AuthCallbackPage />} />

        <Route path="/" element={<ProtectedLayout />}>
          <Route index element={<PageSuspense><Dashboard /></PageSuspense>} />
          <Route path="upload" element={<PageSuspense><UploadPage /></PageSuspense>} />
          <Route path="batch-history" element={<PageSuspense><BatchHistoryPage /></PageSuspense>} />
          <Route path="batch-history/:batchId" element={<PageSuspense><BatchDetailPage /></PageSuspense>} />
          <Route path="documents/:documentId" element={<PageSuspense><DocumentDetailPage /></PageSuspense>} />
          <Route path="candidates" element={<PageSuspense><CandidatesPage /></PageSuspense>} />
          <Route path="audit" element={<PageSuspense><AuditPage /></PageSuspense>} />
          <Route path="review-queue" element={<PageSuspense><ReviewQueuePage /></PageSuspense>} />
          <Route path="settings" element={<PageSuspense><SettingsPage /></PageSuspense>} />
          <Route path="profile" element={<PageSuspense><ProfilePage /></PageSuspense>} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}

export default App;
