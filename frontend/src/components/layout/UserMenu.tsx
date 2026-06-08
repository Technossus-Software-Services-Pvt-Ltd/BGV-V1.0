import { useRef, useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { logoutUser } from '../../api/endpoints';

interface UserMenuProps {
  variant: 'sidebar' | 'mobile';
}

export default function UserMenu({ variant }: UserMenuProps) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

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
      logout();
      setMenuOpen(false);
      navigate('/login', { replace: true });
    }
  };

  const handleOpenProfile = () => {
    setMenuOpen(false);
    navigate('/profile');
  };

  if (variant === 'sidebar') {
    return (
      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen((prev) => !prev)}
          className="w-full flex items-center gap-3 rounded-xl border border-white/[0.08] bg-white/[0.04] px-3 py-2.5 hover:bg-white/[0.08] transition-colors duration-200"
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
          <div className="absolute bottom-14 left-0 right-0 rounded-xl border border-white/[0.08] bg-slate-800/95 backdrop-blur-xl shadow-xl z-20 overflow-hidden">
            <button
              type="button"
              onClick={handleOpenProfile}
              className="w-full px-4 py-2.5 text-left text-sm text-slate-200 hover:bg-white/[0.08] transition-colors"
            >
              Profile
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="w-full px-4 py-2.5 text-left text-sm text-red-300 hover:bg-red-500/20 border-t border-white/[0.08] transition-colors"
            >
              Logout
            </button>
          </div>
        )}
      </div>
    );
  }

  // Mobile variant
  return (
    <div className="relative" ref={menuRef}>
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
        <div className="absolute right-0 top-12 w-56 rounded-xl border border-gray-100 bg-white/95 backdrop-blur-xl shadow-lg z-20 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-900 truncate">{userName}</p>
            <p className="text-xs text-gray-400 truncate">{userEmail}</p>
          </div>
          <button
            type="button"
            onClick={handleOpenProfile}
            className="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Profile
          </button>
          <button
            type="button"
            onClick={handleLogout}
            className="w-full px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50 border-t border-gray-100 transition-colors"
          >
            Logout
          </button>
        </div>
      )}
    </div>
  );
}
