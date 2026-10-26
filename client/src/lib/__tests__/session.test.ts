import axios from 'axios';
import { refreshSession } from '../api';
import { getRefreshToken, getToken, hasSession, setTokens } from '../auth';

const user = { id: 'u1', email: 'c@example.com', role: 'customer', is_active: true, created_at: '2026-10-26' };

beforeEach(() => {
  localStorage.clear();
  jest.restoreAllMocks();
});

describe('refreshSession', () => {
  it('shares one refresh between concurrent callers, because refresh tokens work only once', async () => {
    setTokens({ access_token: 'old', refresh_token: 'am_rt_1' });
    const post = jest.spyOn(axios, 'post').mockResolvedValue({ data: { access_token: 'new', refresh_token: 'am_rt_2', user } });
    const results = await Promise.all([refreshSession(), refreshSession(), refreshSession()]);
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0][1]).toEqual({ refresh_token: 'am_rt_1' });
    expect(results).toEqual(['new', 'new', 'new']);
    expect(getToken()).toBe('new');
    expect(getRefreshToken()).toBe('am_rt_2');
  });

  it('clears the session when the server rejects the refresh token', async () => {
    setTokens({ access_token: 'old', refresh_token: 'am_rt_1' });
    jest.spyOn(axios, 'post').mockRejectedValue({ response: { status: 401 } });
    expect(await refreshSession()).toBeNull();
    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(hasSession()).toBe(false);
  });

  it('keeps the tokens when the server is unreachable, so a later attempt can still succeed', async () => {
    setTokens({ access_token: 'old', refresh_token: 'am_rt_1' });
    jest.spyOn(axios, 'post').mockRejectedValue(new Error('Network Error'));
    expect(await refreshSession()).toBeNull();
    expect(getRefreshToken()).toBe('am_rt_1');
  });

  it('does nothing without a refresh token', async () => {
    const post = jest.spyOn(axios, 'post');
    expect(await refreshSession()).toBeNull();
    expect(post).not.toHaveBeenCalled();
  });
});
