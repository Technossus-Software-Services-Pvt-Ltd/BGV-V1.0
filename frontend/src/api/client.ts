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

// Prevent multiple simultaneous 401 handling
let isHandling401 = false;

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    // Dispatch custom event on 401 so AuthProvider can handle logout via React Router
    if (status === 401 && !isHandling401) {
      isHandling401 = true;
      clearStoredUser();
      window.dispatchEvent(new CustomEvent('auth:session-expired'));
      // Reset flag synchronously — event listeners run synchronously
      isHandling401 = false;
      return Promise.reject(new Error('Session expired'));
    }

    if (status === 401 && isHandling401) {
      return Promise.reject(new Error('Session expired'));
    }

    const message = error.response?.data?.detail || error.message || 'An unexpected error occurred';
    const enhancedError = new Error(message);
    (enhancedError as unknown as { status: number | undefined }).status = status;
    return Promise.reject(enhancedError);
  }
);

export default api;
