import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { clearStoredUser, getStoredUser } from '../utils/auth';
import { logoutUser } from '../api/endpoints';

const navigation = [
  { name: 'Dashboard', path: '/' },
  { name: 'Batch Import', path: '/upload' },
  { name: 'Documents', path: '/documents' },
  { name: 'Candidates', path: '/candidates' },
  { name: 'Audit Logs', path: '/audit' },
  { name: 'Settings', path: '/settings' },
];

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
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

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Link to="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">BGV</span>
              </div>
              <span className="font-semibold text-lg text-gray-900">Verification Platform</span>
            </Link>

            <div className="flex items-center gap-4">
              <nav className="flex gap-1">
                {navigation.map((item) => {
                  const isActive = location.pathname === item.path ||
                    (item.path !== '/' && location.pathname.startsWith(item.path));
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                        isActive
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                      }`}
                    >
                      {item.name}
                    </Link>
                  );
                })}
              </nav>

              <div className="relative" ref={menuRef}>
                <button
                  type="button"
                  onClick={() => setMenuOpen((prev) => !prev)}
                  className="flex items-center gap-2 rounded-lg border border-gray-200 px-2.5 py-1.5 hover:bg-gray-50"
                >
                  {user?.picture ? (
                    <img
                      src={user.picture}
                      alt={userName}
                      className="h-8 w-8 rounded-full object-cover"
                    />
                  ) : (
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-600 text-xs font-semibold text-white">
                      {initials}
                    </div>
                  )}
                  <div className="text-left">
                    <p className="text-sm font-medium text-gray-900 leading-4">{userName}</p>
                    <p className="text-xs text-gray-500 max-w-[160px] truncate">{userEmail}</p>
                  </div>
                </button>

                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-xl border border-gray-200 bg-white shadow-lg z-20">
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
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-sm text-gray-500 text-center">BGV Platform v1.0.0 — AI-Powered Background Verification</p>
        </div>
      </footer>
    </div>
  );
}
