import { AuthUser } from '../types/auth';

const AUTH_USER_KEY = 'bgv_auth_user';

/**
 * Session tokens are now managed via httpOnly cookies set by the backend.
 * The frontend cannot read or write the session token directly — this is
 * intentional to prevent XSS-based token theft.
 *
 * The user profile (non-sensitive) is kept in localStorage for UI display
 * and cross-tab sync via StorageEvent.
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

export function clearStoredUser(): void {
  localStorage.removeItem(AUTH_USER_KEY);
  // Clean up legacy sessionStorage entries from previous implementation
  sessionStorage.removeItem('bgv_auth_session');
}

export function isAuthenticated(): boolean {
  // With httpOnly cookies, we can only check if user profile exists locally.
  // The actual session validity is confirmed on the first API call (401 if expired).
  return !!getStoredUser();
}
