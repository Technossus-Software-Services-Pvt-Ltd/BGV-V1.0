import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { completeGoogleLogin } from '../api/endpoints';
import { isAuthenticated } from '../utils/auth';
import { useAuth } from '../hooks/useAuth';

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login } = useAuth();
  const loginRef = useRef(login);
  loginRef.current = login;
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const providerError = searchParams.get('error');

    if (providerError) {
      navigate(`/login?error=${encodeURIComponent(`Google login failed: ${providerError}`)}`, { replace: true });
      return;
    }

    if (!code || !state) {
      navigate(`/login?error=${encodeURIComponent('Missing OAuth callback parameters. Please sign in again.')}`, { replace: true });
      return;
    }

    const callbackLockKey = `bgv_auth_callback_${state}`;

    if (sessionStorage.getItem(callbackLockKey) === 'done' && isAuthenticated()) {
      navigate('/', { replace: true });
      return;
    }

    sessionStorage.setItem(callbackLockKey, 'pending');

    completeGoogleLogin(code, state)
      .then((response) => {
        // Session cookie is set automatically by the backend response.
        // We only store the non-sensitive user profile for UI display.
        loginRef.current(response.user);
        sessionStorage.setItem(callbackLockKey, 'done');
        navigate('/', { replace: true });
      })
      .catch((err) => {
        sessionStorage.removeItem(callbackLockKey);
        navigate(`/login?error=${encodeURIComponent(err instanceof Error ? err.message : 'Failed to complete sign in')}`, { replace: true });
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center px-4">
      <div className="flex flex-col items-center justify-center">
        <div className="h-14 w-14 animate-spin rounded-full border-4 border-blue-300/30 border-t-blue-400" />
      </div>
    </div>
  );
}
