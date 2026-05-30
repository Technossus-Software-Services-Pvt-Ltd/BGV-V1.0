import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { clearStoredUser, getStoredUser } from '../utils/auth';
import { logoutUser } from '../api/endpoints';

type NavItem = {
  name: string;
  path: string;
  icon: JSX.Element;
};

const navigation: NavItem[] = [
  {
    name: 'Dashboard',
    path: '/',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden="true">
        <rect x="3" y="4" width="8" height="7" rx="1.5" />
        <rect x="13" y="4" width="8" height="7" rx="1.5" />
        <rect x="3" y="13" width="8" height="7" rx="1.5" />
        <rect x="13" y="13" width="8" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    name: 'Batch Import',
    path: '/upload',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden="true">
        <path d="M12 16V4" />
        <path d="M7 9l5-5 5 5" />
        <path d="M4 20h16" />
      </svg>
    ),
  },
  {
    name: 'Documents',
    path: '/documents',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden="true">
        <path d="M8 3h7l5 5v13H8z" />
        <path d="M15 3v5h5" />
        <path d="M11 13h6" />
        <path d="M11 17h6" />
      </svg>
    ),
  },
  {
    name: 'Candidates',
    path: '/candidates',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden="true">
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20c1.8-3 4-4.5 7-4.5s5.2 1.5 7 4.5" />
      </svg>
    ),
  },
  {
    name: 'Audit Logs',
    path: '/audit',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden="true">
        <path d="M4 12a8 8 0 1 0 3-6.2" />
        <path d="M4 4v4h4" />
        <path d="M12 8v5l3 2" />
      </svg>
    ),
  },
  {
    name: 'Settings',
    path: '/settings',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden="true">
        <path d="M12 8.5A3.5 3.5 0 1 1 8.5 12 3.5 3.5 0 0 1 12 8.5Z" />
        <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 0 1 0 2.8 2 2 0 0 1-2.8 0l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 0 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 0 1-2.8 0 2 2 0 0 1 0-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 0 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 0 1 0-2.8 2 2 0 0 1 2.8 0l.1.1a1 1 0 0 0 1.1.2H9a1 1 0 0 0 .6-.9V4a2 2 0 0 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 0 1 2.8 0 2 2 0 0 1 0 2.8l-.1.1a1 1 0 0 0-.2 1.1V9a1 1 0 0 0 .9.6h.2a2 2 0 0 1 0 4h-.2a1 1 0 0 0-.9.6Z" />
      </svg>
    ),
  },
];

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const user = getStoredUser();
  const userName = user?.name?.trim() || user?.email || 'User';
  const userEmail = user?.email || '';

  const initials = useMemo(() => {
    const source = user?.name?.trim() || user?.email || 'U';
    const parts = source.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0][0] || ''}${parts[1][0] || ''}`.toUpperCase();
    }
    return (source.slice(0, 2) || 'U').toUpperCase();
  }, [user?.name, user?.email]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [menuOpen]);

  useEffect(() => {
    setSidebarOpen(false);
    setMenuOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch {
      // Always clear local auth even if network/API logout fails.
    } finally {
      clearStoredUser();
      setMenuOpen(false);
      navigate('/login', { replace: true });
    }
  };

  const handleOpenProfile = () => {
    setMenuOpen(false);
    navigate('/profile');
  };

  const renderNavigation = (isMobileMenu = false) => (
    <nav className="space-y-1.5" aria-label="Main Navigation">
      {navigation.map((item) => {
        const isActive = location.pathname === item.path ||
          (item.path !== '/' && location.pathname.startsWith(item.path));

        return (
          <Link
            key={item.path}
            to={item.path}
            className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-primary-600 text-white'
                : 'text-slate-100/90 hover:bg-white/10 hover:text-white'
            }`}
            onClick={() => {
              if (isMobileMenu) {
                setSidebarOpen(false);
              }
            }}
          >
            <span className={`${isActive ? 'text-white' : 'text-slate-300 group-hover:text-slate-100'}`}>
              {item.icon}
            </span>
            {item.name}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen bg-slate-100 lg:flex">
      <aside className="hidden w-72 shrink-0 bg-slate-950 text-white lg:flex lg:flex-col lg:sticky lg:top-0 lg:h-screen">
        <div className="border-b border-white/10 px-6 py-5">
          <Link to="/" className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-primary-600/90 flex items-center justify-center">
              <span className="text-white font-bold text-sm">BGV</span>
            </div>
            <div>
              <p className="text-xl font-semibold leading-5">DocHire</p>
              <p className="text-sm text-slate-300">Verification Agent</p>
            </div>
          </Link>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6">
          <p className="px-2 pb-2 text-xs font-semibold tracking-[0.2em] text-slate-500">MAIN MENU</p>
          {renderNavigation()}
        </div>

        <div className="border-t border-white/10 p-4">
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((prev) => !prev)}
              className="w-full flex items-center gap-3 rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2.5 hover:bg-slate-900"
            >
              {user?.picture ? (
                <img
                  src={user.picture}
                  alt={userName}
                  className="h-9 w-9 rounded-full object-cover"
                />
              ) : (
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-600 text-xs font-semibold text-white">
                  {initials}
                </div>
              )}
              <div className="min-w-0 text-left">
                <p className="truncate text-sm font-semibold text-white">{userName}</p>
                <p className="truncate text-xs text-slate-300">{userEmail}</p>
              </div>
            </button>

            {menuOpen && (
              <div className="absolute bottom-14 left-0 right-0 rounded-xl border border-white/10 bg-slate-900 shadow-lg z-20">
                <button
                  type="button"
                  onClick={handleOpenProfile}
                  className="w-full px-4 py-2.5 text-left text-sm text-slate-200 hover:bg-white/10"
                >
                  Profile
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full px-4 py-2.5 text-left text-sm text-red-300 hover:bg-red-500/20 border-t border-white/10"
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-gray-200 bg-white/95 backdrop-blur lg:hidden">
          <div className="flex h-16 items-center justify-between px-4 sm:px-6">
            <button
              type="button"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-100"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5" aria-hidden="true">
                <path d="M4 7h16" />
                <path d="M4 12h16" />
                <path d="M4 17h16" />
              </svg>
            </button>

            <Link to="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">BGV</span>
              </div>
              <span className="font-semibold text-gray-900">DocHire</span>
            </Link>

            <button
              type="button"
              aria-label="Open account menu"
              onClick={() => setMenuOpen((prev) => !prev)}
              className="inline-flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-gray-200"
            >
              {user?.picture ? (
                <img
                  src={user.picture}
                  alt={userName}
                  className="h-full w-full object-cover"
                />
              ) : (
                <span className="text-xs font-semibold text-gray-700">{initials}</span>
              )}
            </button>

            {menuOpen && (
              <div className="absolute right-4 top-14 w-56 rounded-xl border border-gray-200 bg-white shadow-lg z-20 sm:right-6">
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-semibold text-gray-900 truncate">{userName}</p>
                  <p className="text-xs text-gray-500 truncate">{userEmail}</p>
                </div>
                <button
                  type="button"
                  onClick={handleOpenProfile}
                  className="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  Profile
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50 border-t border-gray-100"
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        </header>

        {sidebarOpen && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
            <button
              type="button"
              aria-label="Close navigation"
              className="absolute inset-0 bg-slate-950/50"
              onClick={() => setSidebarOpen(false)}
            />
            <aside className="relative h-full w-72 bg-slate-950 text-white shadow-xl">
              <div className="border-b border-white/10 px-4 py-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-sm">BGV</span>
                  </div>
                  <span className="font-semibold text-white">DocHire</span>
                </div>
                <button
                  type="button"
                  aria-label="Close menu"
                  onClick={() => setSidebarOpen(false)}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-slate-200 hover:bg-white/10"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5" aria-hidden="true">
                    <path d="M6 6l12 12" />
                    <path d="M18 6L6 18" />
                  </svg>
                </button>
              </div>
              <div className="px-3 py-4">{renderNavigation(true)}</div>
            </aside>
          </div>
        )}

        <main className="flex-1">
          <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            <Outlet />
          </div>
        </main>

        <footer className="border-t border-gray-200 py-4 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <p className="text-sm text-gray-500 text-center">BGV Platform v1.0.0 - AI-Powered Background Verification</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
