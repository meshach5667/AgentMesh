import { hourlyResourcePrice, isFree, safeExternalUrl, totalsByCurrency } from '../billing';
import type { CostEstimate, Prices } from '@/types';

const prices = (over: Partial<Prices> = {}): Prices => ({
  currency: 'NGN',
  cpu_core_hour: '10.00000000',
  ram_gb_hour: '20.00000000',
  vram_gb_hour: '0E-8',
  input_tokens_per_million: '1000',
  output_tokens_per_million: '2000',
  ...over,
});

describe('pricing helpers', () => {
  it('prices a reservation like the server (1 core + 1 GB = 30/h in tests/test_cost_estimates.py)', () => {
    expect(hourlyResourcePrice(prices(), 1, 1024, 0)).toBe(30);
    expect(hourlyResourcePrice(prices({ vram_gb_hour: '50' }), 2, 2048, 4096)).toBe(2 * 10 + 2 * 20 + 4 * 50);
  });

  it('treats a missing or all-zero price list as free', () => {
    expect(isFree(null)).toBe(true);
    expect(isFree(prices({ cpu_core_hour: '0', ram_gb_hour: '0', input_tokens_per_million: '0', output_tokens_per_million: '0' }))).toBe(true);
    expect(isFree(prices())).toBe(false);
  });

  it('totals estimates per currency and never across currencies', () => {
    const e = (amount: string, currency: string) => ({ amount, currency }) as CostEstimate;
    expect(totalsByCurrency([e('1.5', 'NGN'), e('2.25', 'NGN'), e('3', 'USD')])).toEqual([
      { currency: 'NGN', amount: 3.75 },
      { currency: 'USD', amount: 3 },
    ]);
  });

  it('renders only safe external payment links', () => {
    expect(safeExternalUrl('https://pay.example.com/x?ref=1')).toBe('https://pay.example.com/x?ref=1');
    for (const bad of [
      'http://pay.example.com',
      'javascript:alert(1)',
      'https://user:pw@pay.example.com',
      'https://localhost/x',
      'https://127.0.0.1/x',
      'https://pay.example.com:8443/',
      'https://pay.internal/x',
      'not a url',
      null,
    ]) {
      expect(safeExternalUrl(bad)).toBeNull();
    }
  });
});
