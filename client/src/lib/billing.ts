import type { CostEstimate, Prices } from '@/types';

/** Same formula as Rates.hourly on the server (decimal strings are parsed as numbers for display). */
export function hourlyResourcePrice(rates: Prices, cpuCores: number, ramMb: number, vramMb: number): number {
  return (
    Number(rates.cpu_core_hour) * cpuCores +
    (Number(rates.ram_gb_hour) * ramMb) / 1024 +
    (Number(rates.vram_gb_hour) * vramMb) / 1024
  );
}

export function isFree(rates: Prices | null | undefined): boolean {
  if (!rates) return true;
  return [rates.cpu_core_hour, rates.ram_gb_hour, rates.vram_gb_hour, rates.input_tokens_per_million, rates.output_tokens_per_million].every(
    (v) => Number(v) === 0,
  );
}

/** Totals of estimates per currency (prices are in each provider's own currency, so they are never added across). */
export function totalsByCurrency(estimates: CostEstimate[]): { currency: string; amount: number }[] {
  const totals = new Map<string, number>();
  for (const e of estimates) totals.set(e.currency, (totals.get(e.currency) ?? 0) + Number(e.amount));
  return [...totals.entries()].map(([currency, amount]) => ({ currency, amount })).sort((a, b) => a.currency.localeCompare(b.currency));
}

/**
 * A provider's payment link, re-checked before it is rendered (the server validates it too): https to a public host
 * name, no credentials, standard port. Returns the URL or null.
 */
export function safeExternalUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw);
    const host = u.hostname.toLowerCase();
    if (u.protocol !== 'https:' || u.username || u.password || (u.port && u.port !== '443')) return null;
    if (!host.includes('.') || host === 'localhost' || /^[\d.]+$/.test(host) || host.includes(':') || host.endsWith('.local') || host.endsWith('.internal'))
      return null;
    return u.toString();
  } catch {
    return null;
  }
}
