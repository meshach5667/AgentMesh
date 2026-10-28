'use client';

import Link from 'next/link';
import { useMarket } from '@/hooks/useBilling';
import { money } from '@/lib/format';
import { PRICE_FIELDS } from '@/types';

/** How pricing and payment work, with live price ranges per currency from GET /billing/market. */
export function PricingSection() {
  const { data } = useMarket();
  const range = (min: string, max: string, currency: string) =>
    Number(min) === Number(max) ? money(min, currency) : `${money(min, currency)} – ${money(max, currency)}`;

  return (
    <section id="pricing" className="border-y border-border bg-muted/30 py-28">
      <div className="mx-auto grid max-w-6xl gap-12 px-6 lg:grid-cols-2 lg:items-start">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Pricing and payment</p>
          <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight md:text-[2.75rem] md:leading-[1.1]">
            Providers set the price. You pay them directly.
          </h2>
          <ul className="mt-6 space-y-3 text-muted-foreground">
            <li>Every machine has its own price list, in its provider&apos;s currency: per CPU core-hour, per GB-hour of memory and GPU memory, and per million tokens.</li>
            <li>Your deployment goes to the cheapest machine that fits, within your price limits, and you only owe for time it is ready, plus tokens.</li>
            <li>You buy prepaid credit with a provider, paying them directly through their own Paystack, Flutterwave or Stripe account or by transfer. AgentMesh verifies the payment before their machines serve you, takes no commission, charges no fees and never holds the money.</li>
            <li>Joining is free for customers and providers alike.</li>
          </ul>
        </div>
        <div className="rounded-xl border border-border bg-card p-2 shadow-soft">
          {data && data.nodes > 0 ? (
            <div className="space-y-2 p-3">
              <p className="text-sm">
                <span className="font-semibold tabular-nums">{data.nodes}</span> machine{data.nodes === 1 ? '' : 's'} taking work now
                {data.free_nodes > 0 && <span className="text-muted-foreground"> · {data.free_nodes} free to use</span>}
              </p>
              {data.currencies.map((c) => (
                <div key={c.currency} className="rounded-lg border border-border">
                  <p className="border-b border-border px-4 py-2 text-xs text-muted-foreground">
                    Price range in {c.currency} across {c.nodes} machine{c.nodes === 1 ? '' : 's'}
                  </p>
                  <dl className="divide-y divide-border">
                    {PRICE_FIELDS.map(({ key, label, unit }) => {
                      const r = c.ranges[key];
                      return (
                        <div key={key} className="flex items-baseline justify-between gap-4 px-4 py-2.5">
                          <dt className="text-sm text-muted-foreground">{label}</dt>
                          <dd className="text-right">
                            <span className="font-semibold tabular-nums">{r ? range(r.min, r.max, c.currency) : '—'}</span>{' '}
                            <span className="text-xs text-muted-foreground">{unit}</span>
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                </div>
              ))}
            </div>
          ) : (
            <div className="px-6 py-10 text-center">
              <p className="font-medium">No machines are taking work right now</p>
              <p className="mt-1 text-sm text-muted-foreground">Prices appear here as providers bring machines online.</p>
            </div>
          )}
          <div className="grid gap-2 p-3 sm:grid-cols-2">
            <Link href="/register" className="flex h-10 items-center justify-center rounded-lg bg-primary text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90">
              Start deploying
            </Link>
            <Link href="/register?role=provider" className="flex h-10 items-center justify-center rounded-lg border border-border text-sm font-medium transition-colors hover:bg-muted">
              Offer your machines
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
