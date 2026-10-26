import { create } from 'zustand';
import type { User, UserRole } from '../types/user';
import api, { refreshSession } from '../lib/api';
import { errorMessage } from '../lib/errors';
import { setTokens, removeToken, getToken, getRefreshToken, getCachedUser, setCachedUser, isTokenExpired } from '../lib/auth';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  /** Resolves to an MFA challenge token when the account needs a second factor; then call verifyMfa. */
  login: (email: string, password: string) => Promise<{ mfaToken: string } | void>;
  verifyMfa: (mfaToken: string, code: string) => Promise<void>;
  register: (email: string, password: string, role: UserRole) => Promise<void>;
  logout: () => void;
  initialize: () => Promise<void>;
  clearError: () => void;
}

const signedOut = { user: null, token: null, isAuthenticated: false, isLoading: false };

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

function signIn(set: (state: Partial<AuthState>) => void, data: TokenResponse) {
  setTokens(data);
  setCachedUser(data.user);
  set({ token: data.access_token, user: data.user, isAuthenticated: true, isLoading: false });
}

// One /auth/me check at a time, however many guards mount while it is in flight.
let verifying: Promise<void> | null = null;

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const { data } = await api.post('/auth/login', { email, password });
      if (data.mfa_required) {
        set({ isLoading: false });
        return { mfaToken: data.mfa_token as string };
      }
      signIn(set, data);
    } catch (err) {
      const message = errorMessage(err, 'Login failed');
      set({ error: message, isLoading: false });
      throw new Error(message);
    }
  },

  verifyMfa: async (mfaToken: string, code: string) => {
    set({ isLoading: true, error: null });
    try {
      const { data } = await api.post('/auth/mfa/verify', { mfa_token: mfaToken, code });
      signIn(set, data);
    } catch (err) {
      const message = errorMessage(err, 'Verification failed');
      set({ error: message, isLoading: false });
      throw new Error(message);
    }
  },

  register: async (email: string, password: string, role: UserRole) => {
    set({ isLoading: true, error: null });
    try {
      const { data } = await api.post('/auth/register', { email, password, role });
      signIn(set, data);
    } catch (err) {
      const message = errorMessage(err, 'Registration failed');
      set({ error: message, isLoading: false });
      throw new Error(message);
    }
  },

  /** Ends the session on the server too, so the tokens stop working everywhere, not just in this browser. */
  logout: () => {
    const token = getToken();
    if (token) api.post('/auth/logout', null, { headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined);
    removeToken();
    set({ ...signedOut, error: null });
  },

  /** Restores the stored session at once from the cached user, then confirms it with /auth/me. Only a 401/403
   * signs the user out; a network error or 5xx (for example the API waking up) keeps the session. */
  initialize: async () => {
    let token = getToken();
    if ((!token || isTokenExpired(token)) && getRefreshToken()) {
      token = await refreshSession();
    }
    if (!token || isTokenExpired(token)) {
      if (!getRefreshToken()) removeToken();
      set(signedOut);
      return;
    }
    const cached = getCachedUser();
    if (cached) set({ token, user: cached, isAuthenticated: true, isLoading: false });
    else set({ token });

    if (verifying) return verifying;
    verifying = (async () => {
      try {
        const { data } = await api.get('/auth/me', { headers: { Authorization: `Bearer ${token}` } });
        if (getToken() !== token) return; // signed out or switched accounts meanwhile
        setCachedUser(data);
        set({ user: data, isAuthenticated: true, isLoading: false });
      } catch (err) {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 401 || status === 403) {
          removeToken();
          set(signedOut);
        } else if (!cached) {
          // No cached user to fall back on, so the dashboard cannot pick a role yet; keep the token for a retry.
          set({ isLoading: false, error: errorMessage(err, 'Could not reach the server') });
        }
      } finally {
        verifying = null;
      }
    })();
    return verifying;
  },

  clearError: () => set({ error: null }),
}));
