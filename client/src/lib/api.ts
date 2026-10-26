import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { getRefreshToken, removeToken, setCachedUser, setTokens } from './auth';
import { API_URL } from './config';

const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    if (token && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// One refresh at a time: refresh tokens work once, and reusing one ends the session (reuse detection), so
// concurrent 401s must share a single /auth/refresh call.
let refreshing: Promise<string | null> | null = null;

/** Exchange the stored refresh token for a new pair. Resolves to the new access token, or null when the session is
 * over (the stored tokens are then cleared). */
export function refreshSession(): Promise<string | null> {
  if (refreshing) return refreshing;
  const refreshToken = getRefreshToken();
  if (!refreshToken) return Promise.resolve(null);
  refreshing = (async () => {
    try {
      const { data } = await axios.post(`${API_URL}/auth/refresh`, { refresh_token: refreshToken });
      setTokens(data);
      setCachedUser(data.user);
      return data.access_token as string;
    } catch (err) {
      const status = (err as AxiosError).response?.status;
      if (status === 401 || status === 403) removeToken();
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

const AUTH_PAGES = ['/login', '/register'];

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      const isAuthCall = config?.url?.startsWith('/auth/') && !config.url.startsWith('/auth/me');
      if (config && !config._retried && !isAuthCall) {
        const token = await refreshSession();
        if (token) {
          config._retried = true;
          config.headers.Authorization = `Bearer ${token}`;
          return api.request(config);
        }
      }
      if (!isAuthCall) {
        removeToken();
        if (!AUTH_PAGES.includes(window.location.pathname)) {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
