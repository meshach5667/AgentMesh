import type { Charge, PricingRule } from '@/types';

/** Same formula as billing_service.hourly_resource_price (decimal strings are parsed as numbers for display). */
export function hourlyResourcePrice(rule: PricingRule, cpuCores: number, ramMb: number, vramMb: number): number {
  return (
    Number(rule.cpu_core_hour) * cpuCores +
    (Number(rule.ram_gb_hour) * ramMb) / 1024 +
    (Number(rule.vram_gb_hour) * vramMb) / 1024
  );
}

export function isFree(rule: PricingRule | null | undefined): boolean {
  if (!rule) return true;
  return [rule.cpu_core_hour, rule.ram_gb_hour, rule.vram_gb_hour, rule.input_tokens_per_million, rule.output_tokens_per_million].every(
    (v) => Number(v) === 0,
  );
}

/** A commission rate such as "0.1000" as "10%" (one decimal place only when needed). */
export function percent(rate: string | number | null | undefined): string {
  if (rate == null || rate === '') return '—';
  const p = Math.round(Number(rate) * 1000) / 10;
  return `${Number.isInteger(p) ? p.toFixed(0) : p.toFixed(1)}%`;
}

/** The provider's share of a charge at a given commission rate, e.g. "0.1" -> "90%". */
export function providerShare(rate: string | number | null | undefined): string {
  return rate == null || rate === '' ? '—' : percent(1 - Number(rate));
}

/** The rate a charge was split at; older charges without a recorded rate get it from their own amounts. */
export function chargeFeeRate(charge: Charge): number | null {
  if (charge.platform_fee_rate != null) return Number(charge.platform_fee_rate);
  return Number(charge.amount) > 0 ? Number(charge.platform_fee) / Number(charge.amount) : null;
}

export function sumAmounts(charges: Charge[], field: 'amount' | 'provider_amount' | 'platform_fee' = 'amount'): number {
  return charges.reduce((t, c) => t + Number(c[field]), 0);
}

/** Paystack appends ?reference=...&trxref=... when it returns the customer to the callback URL. */
export function returnedReference(params: URLSearchParams): string | null {
  const ref = params.get('reference') || params.get('trxref');
  return ref && /^am-top-[0-9a-f]{24}$/.test(ref) ? ref : null;
}

/** Only send customers to Paystack's own checkout (never to a URL an attacker could have planted). */
export function isPaystackCheckout(url: string | null | undefined): url is string {
  if (!url) return false;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && (u.hostname === 'checkout.paystack.com' || u.hostname.endsWith('.paystack.com'));
  } catch {
    return false;
  }
}
