import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { completeGoogleLogin } from '../api/endpoints';
import { isAuthenticated, setSessionToken, setStoredUser } from '../utils/auth';

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const runCallback = async () => {
      const redirectToLoginWithError = (message: string) => {
        navigate(`/login?error=${encodeURIComponent(message)}`, { replace: true });
      };

      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const providerError = searchParams.get('error');

      if (providerError) {
        redirectToLoginWithError(`Google login failed: ${providerError}`);
        return;
      }

      if (!code || !state) {
        redirectToLoginWithError('Missing OAuth callback parameters. Please sign in again.');
        return;
      }

      const callbackLockKey = `bgv_auth_callback_${state}`;
      const callbackStatus = sessionStorage.getItem(callbackLockKey);

      if (callbackStatus === 'done' && isAuthenticated()) {
        navigate('/', { replace: true });
        return;
      }

      if (callbackStatus === 'pending') {
        return;
      }

      sessionStorage.setItem(callbackLockKey, 'pending');

      try {
        const response = await completeGoogleLogin(code, state);
        setStoredUser(response.user);
        setSessionToken(response.session_token);
        sessionStorage.setItem(callbackLockKey, 'done');
        navigate('/', { replace: true });
      } catch (err) {
        sessionStorage.removeItem(callbackLockKey);
        redirectToLoginWithError(err instanceof Error ? err.message : 'Failed to complete sign in');
      }
    };

    runCallback();
  }, [navigate, searchParams]);

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center px-4">
      <div className="flex flex-col items-center justify-center">
        <div className="h-14 w-14 animate-spin rounded-full border-4 border-blue-300/30 border-t-blue-400" />
      </div>
    </div>
  );
}
