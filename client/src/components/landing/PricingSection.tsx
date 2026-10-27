'use client';

import Link from 'next/link';
import { useMarket } from '@/hooks/useBilling';
import { providerShare } from '@/lib/billing';
import { money } from '@/lib/format';
import { PRICE_FIELDS } from '@/types';

/** How pricing works, with live price ranges across machines from GET /billing/market. */
export function PricingSection() {
  const { data } = useMarket();
  const hasRanges = !!data && data.nodes > 0 && Object.keys(data.ranges).length > 0;
  const range = (min: string, max: string) =>
    Number(min) === Number(max) ? money(min, data?.currency) : `${money(min, data?.currency)} – ${money(max, data?.currency)}`;

  return (
    <section id="pricing" className="py-28">
      <div className="mx-auto grid max-w-6xl gap-12 px-6 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Pricing</p>
          <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight md:text-[2.75rem] md:leading-[1.1]">
            Providers set the price. You set the limit.
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Every machine on AgentMesh has its own price list, set by the provider who runs it. Your deployment goes to
            the cheapest machine that fits, never one above your price limits, and you pay only while it is ready, plus
            the tokens it processes. Downloads, startup and unhealthy time are free.
          </p>
          <p className="mt-4 text-sm text-muted-foreground">
            Prepaid from your wallet. You never pay more than the prices in force when your deployment was placed, and
            providers receive {data ? providerShare(data.commission_rate) : 'most'} of every charge.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-2 shadow-soft">
          {hasRanges ? (
            <>
              <div className="divide-y divide-border">
                {PRICE_FIELDS.map(({ key, label, unit }) => {
                  const r = data.ranges[key];
                  return (
                    <div key={key} className="flex items-baseline justify-between gap-4 px-5 py-4">
                      <span className="text-sm text-muted-foreground">{label}</span>
                      <span className="text-right">
                        <span className="font-semibold tabular-nums">{r ? range(r.min, r.max) : '—'}</span>{' '}
                        <span className="text-xs text-muted-foreground">{unit}</span>
                      </span>
                    </div>
                  );
                })}
              </div>
              <p className="px-5 pb-4 pt-2 text-xs text-muted-foreground">
                Live range across {data.nodes} machine{data.nodes === 1 ? '' : 's'} taking work now.
              </p>
            </>
          ) : (
            <div className="px-6 py-10 text-center">
              <p className="font-medium">No machines are taking work right now</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Prices appear here as providers bring machines online. Each provider sets their own.
              </p>
            </div>
          )}
          <div className="grid gap-2 p-3 sm:grid-cols-2">
            <Link href="/register" className="flex h-10 items-center justify-center rounded-lg bg-primary text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90">
              Start deploying
            </Link>
            <Link href="/register?role=provider" className="flex h-10 items-center justify-center rounded-lg border border-border text-sm font-medium transition-colors hover:bg-muted">
              Set your own prices
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
