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
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_35%_35%,rgba(37,99,235,0.25),transparent_40%),radial-gradient(circle_at_80%_20%,rgba(59,130,246,0.2),transparent_35%),linear-gradient(135deg,#020617_0%,#0b1b4d_55%,#1d2f70_100%)]" />
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 py-10">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600 shadow-xl shadow-blue-600/30">
            <span className="text-2xl text-white">🛡️</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-white">BGV classification Agent</h1>
          <p className="mt-2 text-lg text-blue-200">Background Verification Agent</p>
        </div>

        <div className="w-full max-w-md rounded-3xl border border-white/10 bg-white/10 p-8 shadow-2xl backdrop-blur-xl">
          <h2 className="text-center text-3xl font-semibold text-white">Welcome Back</h2>
          <p className="mt-2 text-center text-sm text-blue-100">Sign in to access your verification dashboard</p>

          {error && (
            <div className="mt-6 rounded-lg border border-red-300/30 bg-red-500/20 px-4 py-3 text-sm text-red-100">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={isLoading}
            className="mt-8 flex w-full items-center justify-center gap-3 rounded-xl bg-white px-4 py-3 text-base font-semibold text-gray-800 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
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

        <p className="mt-8 text-sm text-blue-200/80">© 2026 BGV classification Agent. All rights reserved.</p>
      </div>
    </div>
  );
}
