import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { startGoogleLogin } from '../api/endpoints';
import { isAuthenticated } from '../utils/auth';

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated()) {
      navigate('/', { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    const errorMessage = searchParams.get('error');
    if (errorMessage) {
      setError(errorMessage);
    }
  }, [searchParams]);

  const handleGoogleLogin = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await startGoogleLogin(`${window.location.origin}/auth/callback`);
      window.location.href = response.oauth_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start Google sign in');
      setIsLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_35%_35%,rgba(79,70,229,0.25),transparent_40%),radial-gradient(circle_at_80%_20%,rgba(99,102,241,0.2),transparent_35%),linear-gradient(135deg,#020617_0%,#1e1b4b_55%,#312e81_100%)]" />
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 py-10">
        <div className="mb-10 text-center">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-xl shadow-primary-900/40">
            <span className="text-2xl text-white">🛡️</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-white tracking-tight">BGV Platform</h1>
          <p className="mt-2 text-lg text-primary-200/80 font-medium">AI-Powered Background Verification</p>
        </div>

        <div className="w-full max-w-md rounded-3xl border border-white/[0.08] bg-white/[0.08] p-8 shadow-2xl backdrop-blur-xl">
          <h2 className="text-center text-2xl font-bold text-white tracking-tight">Welcome Back</h2>
          <p className="mt-2 text-center text-sm text-primary-200/70">Sign in to access your verification dashboard</p>

          {error && (
            <div className="mt-6 rounded-xl border border-rose-300/20 bg-rose-500/15 px-4 py-3 text-sm text-rose-200">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={isLoading}
            className="mt-8 flex w-full items-center justify-center gap-3 rounded-xl bg-white px-4 py-3.5 text-base font-semibold text-gray-800 shadow-lg transition-all duration-200 hover:bg-gray-50 hover:shadow-xl hover:scale-[1.01] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
              <path
                fill="#4285F4"
                d="M23.49 12.27c0-.79-.07-1.55-.2-2.27H12v4.3h6.44a5.5 5.5 0 0 1-2.39 3.61v3h3.86c2.26-2.08 3.58-5.14 3.58-8.64Z"
              />
              <path
                fill="#34A853"
                d="M12 24c3.24 0 5.95-1.07 7.93-2.89l-3.86-3A7.18 7.18 0 0 1 12 19.3a7.2 7.2 0 0 1-6.75-4.98H1.26v3.12A12 12 0 0 0 12 24Z"
              />
              <path
                fill="#FBBC05"
                d="M5.25 14.32A7.2 7.2 0 0 1 4.87 12c0-.81.14-1.6.38-2.32V6.56H1.26A12 12 0 0 0 0 12c0 1.94.46 3.78 1.26 5.44l3.99-3.12Z"
              />
              <path
                fill="#EA4335"
                d="M12 4.77c1.76 0 3.34.61 4.58 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.26 6.56l3.99 3.12A7.2 7.2 0 0 1 12 4.77Z"
              />
            </svg>
            {isLoading ? 'Redirecting...' : 'Sign in with Google'}
          </button>
        </div>

        <p className="mt-8 text-sm text-primary-200/50 font-medium">© 2026 BGV Platform. All rights reserved.</p>
      </div>
    </div>
  );
}
