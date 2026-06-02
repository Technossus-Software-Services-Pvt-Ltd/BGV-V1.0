import axios from 'axios';
import { getSessionToken, clearStoredUser } from '../utils/auth';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = getSessionToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
    config.headers['x-session-token'] = token;
  }
  return config;
});

// Prevent multiple simultaneous 401 redirects
let isRedirecting = false;

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    // Auto-redirect to login on 401 (session expired/invalid)
    if (status === 401 && !isRedirecting) {
      isRedirecting = true;
      clearStoredUser();
      window.location.href = '/login';
      // Return a never-resolving promise to prevent downstream error handlers
      return new Promise(() => {});
    }

    // If already redirecting, suppress additional 401 errors
    if (status === 401 && isRedirecting) {
      return new Promise(() => {});
    }

    const message = error.response?.data?.detail || error.message || 'An unexpected error occurred';
    const enhancedError = new Error(message);
    (enhancedError as unknown as { status: number | undefined }).status = status;
    return Promise.reject(enhancedError);
  }
);

export default api;
