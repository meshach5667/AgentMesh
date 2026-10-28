'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PRICE_FIELDS, type PriceField, type Prices } from '@/types';

const MAX_PRICE = 1_000_000;
export const COMMON_CURRENCIES = ['NGN', 'USD', 'EUR', 'GBP', 'KES', 'GHS', 'ZAR', 'INR', 'CAD'];

function initialValues(initial: Prices | null, currency: string): Prices {
  const n = (v: string | undefined) => String(Number(v ?? 0));
  return {
    currency: initial?.currency ?? currency,
    cpu_core_hour: n(initial?.cpu_core_hour),
    ram_gb_hour: n(initial?.ram_gb_hour),
    vram_gb_hour: n(initial?.vram_gb_hour),
    input_tokens_per_million: n(initial?.input_tokens_per_million),
    output_tokens_per_million: n(initial?.output_tokens_per_million),
  };
}

export function priceError(v: string): string | null {
  const t = v.trim();
  if (t === '') return 'Enter a price (0 for free).';
  if (!/^\d+(\.\d{1,8})?$/.test(t)) return 'Use a number like 12 or 0.5, with at most 8 decimals.';
  if (Number(t) > MAX_PRICE) return `At most ${MAX_PRICE.toLocaleString()}.`;
  return null;
}

export function currencyError(v: string): string | null {
  return /^[A-Z]{3}$/.test(v.trim()) ? null : 'Use a 3-letter ISO currency code, such as NGN or USD.';
}

/** Edit a machine's price list: what customers pay the provider directly, per unit, in the chosen currency. */
export function PriceListForm({
  initial,
  defaultCurrency = 'NGN',
  submitLabel,
  pending,
  onSubmit,
  children,
  idPrefix = 'price',
}: {
  initial: Prices | null;
  defaultCurrency?: string;
  submitLabel: string;
  pending: boolean;
  onSubmit: (prices: Prices) => void;
  children?: React.ReactNode;
  idPrefix?: string;
}) {
  const [values, setValues] = useState<Prices>(() => initialValues(initial, defaultCurrency));
  const [touched, setTouched] = useState(false);
  const errors = Object.fromEntries(PRICE_FIELDS.map(({ key }) => [key, priceError(values[key])])) as Record<PriceField, string | null>;
  const curError = currencyError(values.currency);
  const valid = !curError && PRICE_FIELDS.every(({ key }) => !errors[key]);

  const set = (key: keyof Prices, v: string) => setValues((cur) => ({ ...cur, [key]: key === 'currency' ? v.toUpperCase() : v }));
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!valid) return;
    onSubmit({
      currency: values.currency.trim(),
      cpu_core_hour: values.cpu_core_hour.trim(),
      ram_gb_hour: values.ram_gb_hour.trim(),
      vram_gb_hour: values.vram_gb_hour.trim(),
      input_tokens_per_million: values.input_tokens_per_million.trim(),
      output_tokens_per_million: values.output_tokens_per_million.trim(),
    });
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="max-w-[12rem] space-y-1.5">
        <Label htmlFor={`${idPrefix}-currency`}>Currency</Label>
        <Input
          id={`${idPrefix}-currency`}
          list={`${idPrefix}-currencies`}
          value={values.currency}
          maxLength={3}
          onChange={(e) => set('currency', e.target.value)}
          aria-invalid={touched && !!curError}
          aria-describedby={`${idPrefix}-currency-help`}
        />
        <datalist id={`${idPrefix}-currencies`}>
          {COMMON_CURRENCIES.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
        <p id={`${idPrefix}-currency-help`} className={touched && curError ? 'text-xs text-destructive' : 'text-xs text-muted-foreground'}>
          {touched && curError ? curError : 'The currency customers pay you in.'}
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PRICE_FIELDS.map(({ key, label, unit }) => {
          const err = errors[key];
          const show = touched || values[key] !== initialValues(initial, defaultCurrency)[key];
          return (
            <div key={key} className="space-y-1.5">
              <Label htmlFor={`${idPrefix}-${key}`}>
                {label} <span className="font-normal text-muted-foreground">({unit})</span>
              </Label>
              <Input
                id={`${idPrefix}-${key}`}
                inputMode="decimal"
                value={values[key]}
                onChange={(e) => set(key, e.target.value)}
                aria-invalid={show && !!err}
                aria-describedby={err && show ? `${idPrefix}-${key}-error` : undefined}
              />
              {err && show && (
                <p id={`${idPrefix}-${key}-error`} className="text-xs text-destructive">
                  {err}
                </p>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Customers pay you these prices directly, using the payment arrangement on your profile. AgentMesh takes no
        commission and processes no payments. Set every price to 0 to offer the machine free.
      </p>
      {children}
      <Button type="submit" disabled={pending}>
        {pending ? 'Saving…' : submitLabel}
      </Button>
    </form>
  );
}
