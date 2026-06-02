import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import UploadPage from './pages/UploadPage';
import BatchHistoryPage from './pages/BatchHistoryPage';
import BatchDetailPage from './pages/BatchDetailPage';
import DocumentDetailPage from './pages/DocumentDetailPage';
import CandidatesPage from './pages/CandidatesPage';
import AuditPage from './pages/AuditPage';
import ReviewQueuePage from './pages/ReviewQueuePage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import AuthCallbackPage from './pages/AuthCallbackPage';
import { useAuth } from './hooks/useAuth';
import ProfilePage from './pages/ProfilePage';

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
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />

      <Route path="/" element={<ProtectedLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="batch-history" element={<BatchHistoryPage />} />
        <Route path="batch-history/:batchId" element={<BatchDetailPage />} />
        <Route path="documents/:documentId" element={<DocumentDetailPage />} />
        <Route path="candidates" element={<CandidatesPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="review-queue" element={<ReviewQueuePage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
