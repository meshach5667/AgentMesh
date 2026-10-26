import api, { refreshSession } from '../../lib/api';
import { getToken, isTokenExpired, setCachedUser, setToken } from '../../lib/auth';
import { useAuthStore } from '../authStore';

jest.mock('../../lib/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() }, refreshSession: jest.fn() }));
const get = api.get as jest.Mock;
const post = api.post as jest.Mock;
const refresh = refreshSession as jest.Mock;

const user = { id: 'u1', email: 'c@example.com', role: 'customer' as const, is_active: true, created_at: '2026-01-01' };
const jwt = (exp: number) => `h.${btoa(JSON.stringify({ sub: 'u1', exp })).replace(/=+$/, '')}.s`;
const future = () => jwt(Math.floor(Date.now() / 1000) + 3600);

beforeEach(() => {
  localStorage.clear();
  get.mockReset();
  post.mockReset().mockResolvedValue({});
  refresh.mockReset();
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false, isLoading: true, error: null });
});

describe('auth session', () => {
  it('restores the cached user immediately and keeps the session when the API is unreachable', async () => {
    setToken(future());
    setCachedUser(user);
    get.mockRejectedValue(new Error('Network Error'));
    const pending = useAuthStore.getState().initialize();
    expect(useAuthStore.getState()).toMatchObject({ isAuthenticated: true, isLoading: false, user });
    await pending;
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(getToken()).not.toBeNull();
  });

  it('signs out only when the API rejects the token', async () => {
    setToken(future());
    setCachedUser(user);
    get.mockRejectedValue({ response: { status: 401 } });
    await useAuthStore.getState().initialize();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(getToken()).toBeNull();
  });

  it('keeps the token for a retry when there is no cached user and the API is down', async () => {
    setToken(future());
    get.mockRejectedValue({ response: { status: 503 } });
    await useAuthStore.getState().initialize();
    expect(useAuthStore.getState()).toMatchObject({ isAuthenticated: false, isLoading: false });
    expect(useAuthStore.getState().token).not.toBeNull();
    expect(getToken()).not.toBeNull();
  });

  it('drops an expired token without calling the API', async () => {
    setToken(jwt(Math.floor(Date.now() / 1000) - 10));
    await useAuthStore.getState().initialize();
    expect(get).not.toHaveBeenCalled();
    expect(getToken()).toBeNull();
  });

  it('shares one /auth/me call between guards that mount together', async () => {
    setToken(future());
    get.mockResolvedValue({ data: user });
    await Promise.all([useAuthStore.getState().initialize(), useAuthStore.getState().initialize()]);
    expect(get).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().user).toEqual(user);
  });

  it('renews an expired access token with the refresh token before checking the session', async () => {
    setToken(jwt(Math.floor(Date.now() / 1000) - 10));
    localStorage.setItem('refresh_token', 'am_rt_x');
    const fresh = future();
    refresh.mockImplementation(async () => {
      localStorage.setItem('token', fresh);
      return fresh;
    });
    get.mockResolvedValue({ data: user });
    await useAuthStore.getState().initialize();
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith('/auth/me', { headers: { Authorization: `Bearer ${fresh}` } });
    expect(useAuthStore.getState()).toMatchObject({ isAuthenticated: true, user });
  });

  it('signs out when the refresh token is no longer accepted', async () => {
    setToken(jwt(Math.floor(Date.now() / 1000) - 10));
    localStorage.setItem('refresh_token', 'am_rt_x');
    refresh.mockImplementation(async () => {
      localStorage.clear();
      return null;
    });
    await useAuthStore.getState().initialize();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(get).not.toHaveBeenCalled();
  });

  it('ends the session on the server at logout', () => {
    const token = future();
    setToken(token);
    localStorage.setItem('refresh_token', 'am_rt_x');
    useAuthStore.getState().logout();
    expect(post).toHaveBeenCalledWith('/auth/logout', null, { headers: { Authorization: `Bearer ${token}` } });
    expect(getToken()).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });

  it('treats undecodable tokens as not expired so the API decides', () => {
    expect(isTokenExpired('not-a-jwt')).toBe(false);
  });
});
