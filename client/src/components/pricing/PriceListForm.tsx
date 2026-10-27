'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { money } from '@/lib/format';
import { PRICE_FIELDS, type PriceField, type Prices } from '@/types';

const MAX_PRICE = 1_000_000;
const ZERO: Prices = {
  cpu_core_hour: '0',
  ram_gb_hour: '0',
  vram_gb_hour: '0',
  input_tokens_per_million: '0',
  output_tokens_per_million: '0',
};

function mapPrices(f: (key: PriceField) => string): Prices {
  return {
    cpu_core_hour: f('cpu_core_hour'),
    ram_gb_hour: f('ram_gb_hour'),
    vram_gb_hour: f('vram_gb_hour'),
    input_tokens_per_million: f('input_tokens_per_million'),
    output_tokens_per_million: f('output_tokens_per_million'),
  };
}

function valid(v: string): boolean {
  if (v.trim() === '' || !/^\d+(\.\d{1,8})?$/.test(v.trim())) return false;
  return Number(v) <= MAX_PRICE;
}

/** Edit a price list. Shows what the provider keeps of each price after the platform commission. */
export function PriceListForm({
  initial,
  currency,
  commissionRate,
  submitLabel,
  pending,
  onSubmit,
  children,
  idPrefix = 'price',
}: {
  initial: Prices | null;
  currency: string;
  commissionRate: string | null;
  submitLabel: string;
  pending: boolean;
  onSubmit: (prices: Prices) => void;
  children?: React.ReactNode;
  idPrefix?: string;
}) {
  const [values, setValues] = useState<Prices>(() => {
    const start = initial ?? ZERO;
    return mapPrices((key) => String(Number(start[key])));
  });
  const allValid = PRICE_FIELDS.every(({ key }) => valid(values[key]));
  const keep = 1 - Number(commissionRate ?? 0);

  const set = (key: PriceField, v: string) => setValues((cur) => ({ ...cur, [key]: v }));
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (allValid) onSubmit(mapPrices((key) => values[key].trim()));
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PRICE_FIELDS.map(({ key, label, unit }) => {
          const ok = valid(values[key]);
          return (
            <div key={key} className="space-y-1.5">
              <Label htmlFor={`${idPrefix}-${key}`}>
                {label} <span className="font-normal text-muted-foreground">({currency} {unit})</span>
              </Label>
              <Input
                id={`${idPrefix}-${key}`}
                inputMode="decimal"
                value={values[key]}
                onChange={(e) => set(key, e.target.value)}
                aria-invalid={!ok}
              />
              <p className="text-xs text-muted-foreground">
                {ok ? `You keep ${money(Number(values[key]) * keep, currency)}` : `A number from 0 to ${MAX_PRICE.toLocaleString()}`}
              </p>
            </div>
          );
        })}
      </div>
      {children}
      <Button type="submit" disabled={!allValid || pending}>
        {pending ? 'Saving…' : submitLabel}
      </Button>
    </form>
  );
}
