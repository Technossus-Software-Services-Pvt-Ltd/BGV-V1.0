import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { SidebarNav, UserMenu, MobileDrawer } from './layout/index';

export default function Layout() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-gray-50/80 lg:flex">
      <aside className="hidden w-[17rem] shrink-0 bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 text-white lg:flex lg:flex-col lg:sticky lg:top-0 lg:h-screen">
        <div className="border-b border-white/[0.08] px-6 py-5">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-lg shadow-primary-900/30 transition-transform duration-200 group-hover:scale-105">
              <span className="text-white font-bold text-sm">BGV</span>
            </div>
            <div>
              <p className="text-lg font-bold leading-5 tracking-tight">BGV Platform</p>
              <p className="text-xs text-slate-400 font-medium">Verification Agent</p>
            </div>
          </Link>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6">
          <p className="px-3 pb-3 text-[10px] font-bold tracking-[0.2em] text-slate-500 uppercase">Main Menu</p>
          <SidebarNav />
        </div>

        <div className="border-t border-white/[0.08] p-4">
          <UserMenu variant="sidebar" />
        </div>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-gray-200/60 bg-white/80 backdrop-blur-xl lg:hidden">
          <div className="flex h-16 items-center justify-between px-4 sm:px-6">
            <button
              type="button"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5" aria-hidden="true">
                <path d="M4 7h16" />
                <path d="M4 12h16" />
                <path d="M4 17h16" />
              </svg>
            </button>

            <Link to="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center shadow-sm">
                <span className="text-white font-bold text-xs">BGV</span>
              </div>
              <span className="font-bold text-gray-900">BGV Platform</span>
            </Link>

            <UserMenu variant="mobile" />
          </div>
        </header>

        <MobileDrawer open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        <main className="flex-1">
          <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8 animate-fade-in">
            <Outlet />
          </div>
        </main>

        <footer className="border-t border-gray-200/60 py-4 bg-white/60 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <p className="text-xs text-gray-400 text-center font-medium">BGV Platform v1.0.0 — AI-Powered Background Verification</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
