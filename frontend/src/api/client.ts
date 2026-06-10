import axios from 'axios';
import { clearStoredUser } from '../utils/auth';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  // Send httpOnly session cookie automatically with every request
  withCredentials: true,
});

// Prevent multiple simultaneous 401 handling
let isHandling401 = false;

api.interceptors.response.use(
  (response) => {
    // Reset 401 flag on successful response (allows re-login in same SPA session)
    isHandling401 = false;
    return response;
  },
  (error) => {
    const status = error.response?.status;

    // Dispatch custom event on 401 so AuthProvider can handle logout via React Router
    if (status === 401 && !isHandling401) {
      isHandling401 = true;
      clearStoredUser();
      window.dispatchEvent(new CustomEvent('auth:session-expired'));
      // Don't reset — the page will redirect to /login. Flag resets on next full page load.
      return Promise.reject(new Error('Session expired'));
    }

    if (status === 401) {
      return Promise.reject(new Error('Session expired'));
    }

    const message = error.response?.data?.detail || error.message || 'An unexpected error occurred';
    const enhancedError = new Error(message);
    (enhancedError as unknown as { status: number | undefined }).status = status;
    return Promise.reject(enhancedError);
  }
);

export default api;
