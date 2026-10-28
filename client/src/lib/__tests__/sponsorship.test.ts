import { clickUrl, dismiss, dismissedIds, promotionLabel } from '../sponsorship';

const ID = '3f2b8c1e-9a4d-4e7b-8c2a-1d5e6f7a8b9c';

function memoryStorage(initial: Record<string, string> = {}) {
  const data = { ...initial };
  return { getItem: (k: string) => data[k] ?? null, setItem: (k: string, v: string) => void (data[k] = v), data };
}

describe('clickUrl', () => {
  it('builds the absolute click URL for an API click path', () => {
    expect(clickUrl(`/api/v1/sponsored/${ID}/click?placement=landing&token=t`, 'https://api.example/')).toBe(
      `https://api.example/api/v1/sponsored/${ID}/click?placement=landing&token=t`,
    );
  });

  it.each(['https://evil.example/', '//evil.example/x', `/api/v1/sponsored/${ID}/impression?x=1`, `javascript:alert(1)`, `/api/v1/sponsored/not-an-id/click?x`])(
    'rejects %s',
    (path) => expect(clickUrl(path, 'https://api.example')).toBeNull(),
  );
});

describe('dismissed sponsored items', () => {
  it('remembers dismissed ids', () => {
    const storage = memoryStorage();
    dismiss('a', storage);
    dismiss('b', storage);
    expect(dismissedIds(storage)).toEqual(['a', 'b']);
  });

  it('keeps only the latest 50', () => {
    const storage = memoryStorage();
    for (let i = 0; i < 60; i++) dismiss(String(i), storage);
    const ids = dismissedIds(storage);
    expect(ids).toHaveLength(50);
    expect(ids[49]).toBe('59');
  });

  it('ignores corrupt or hostile stored values', () => {
    expect(dismissedIds(memoryStorage({ 'agentmesh.sponsored.dismissed': '{not json' }))).toEqual([]);
    expect(dismissedIds(memoryStorage({ 'agentmesh.sponsored.dismissed': '{"a":1}' }))).toEqual([]);
    expect(dismissedIds(memoryStorage({ 'agentmesh.sponsored.dismissed': '["a",2,null]' }))).toEqual(['a']);
  });

  it('survives storage that throws (private windows)', () => {
    const throwing = {
      getItem: () => {
        throw new Error('denied');
      },
      setItem: () => {
        throw new Error('denied');
      },
    };
    expect(dismissedIds(throwing)).toEqual([]);
    expect(() => dismiss('a', throwing)).not.toThrow();
  });
});

it('labels every promoted item', () => {
  expect(promotionLabel('sponsored')).toBe('Sponsored');
  expect(promotionLabel('referral')).toBe('Referral link');
  expect(promotionLabel(undefined)).toBe('Sponsored');
});
