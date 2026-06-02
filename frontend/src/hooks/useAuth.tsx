import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { AuthUser } from '../types/auth';
import {
  getStoredUser,
  setStoredUser as storeUser,
  getSessionToken,
  setSessionToken as storeToken,
  clearStoredUser as clearAuth,
  isAuthenticated as checkAuth,
} from '../utils/auth';

interface AuthContextValue {
  user: AuthUser | null;
  isLoggedIn: boolean;
  login: (user: AuthUser, token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoggedIn: false,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
  const [isLoggedIn, setIsLoggedIn] = useState(() => checkAuth());

  // Sync auth state on storage events (e.g., logout in another tab)
  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === 'bgv_auth_user' || event.key === 'bgv_auth_session' || event.key === null) {
        setUser(getStoredUser());
        setIsLoggedIn(checkAuth());
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const login = useCallback((newUser: AuthUser, token: string) => {
    storeUser(newUser);
    storeToken(token);
    setUser(newUser);
    setIsLoggedIn(true);
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    setIsLoggedIn(false);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoggedIn, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
