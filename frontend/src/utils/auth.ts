import { AuthUser } from '../types/auth';

const AUTH_USER_KEY = 'bgv_auth_user';
const AUTH_SESSION_KEY = 'bgv_auth_session';

/**
 * Session token is stored in sessionStorage (not localStorage) to reduce exposure:
 * - sessionStorage is cleared when the tab/window closes
 * - Not shared across tabs (limits blast radius of XSS)
 * - User profile is kept in localStorage for cross-tab sync (non-sensitive data)
 *
 * NOTE: For production hardening, migrate to httpOnly cookies set by the backend.
 */

export function getStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setStoredUser(user: AuthUser): void {
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

export function getSessionToken(): string | null {
  return sessionStorage.getItem(AUTH_SESSION_KEY);
}

export function setSessionToken(token: string): void {
  sessionStorage.setItem(AUTH_SESSION_KEY, token);
  // Remove from localStorage if previously stored there (migration)
  localStorage.removeItem(AUTH_SESSION_KEY);
}

export function clearStoredUser(): void {
  localStorage.removeItem(AUTH_USER_KEY);
  localStorage.removeItem(AUTH_SESSION_KEY);
  sessionStorage.removeItem(AUTH_SESSION_KEY);
}

export function isAuthenticated(): boolean {
  return !!getStoredUser() && !!getSessionToken();
}
