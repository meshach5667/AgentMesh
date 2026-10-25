'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorState } from '@/components/common/Notices';
import { useBillingSummary } from '@/hooks/useBilling';
import { percent } from '@/lib/billing';
import { errorMessage } from '@/lib/errors';
import { money } from '@/lib/format';
import type { BillingScope } from '@/types';

const TEXT: Record<BillingScope, { title: string; description: string; gross: string; share: string }> = {
  customer: {
    title: 'Where your money went',
    description: 'Your compute charges, split between the providers whose machines ran them and the platform commission.',
    gross: 'You were charged',
    share: 'Paid to providers',
  },
  provider: {
    title: 'Fee breakdown',
    description: 'What customers paid for deployments on your nodes, the platform commission, and what you were credited.',
    gross: 'Customers paid',
    share: 'Credited to you',
  },
  network: {
    title: 'Compute revenue',
    description: 'All rated compute charges on the network: provider earnings and platform commission.',
    gross: 'Customers paid',
    share: 'Provider earnings',
  },
};

/** Gross / platform commission / provider share of rated charges over a period, from GET /billing/summary. */
export function FeeBreakdown({ days = 30, scope }: { days?: number; scope?: BillingScope }) {
  const summary = useBillingSummary(days, scope);
  if (summary.error) return <ErrorState message={errorMessage(summary.error)} />;
  if (!summary.data) return null;
  const { totals, currency } = summary.data;
  const text = TEXT[summary.data.scope];
  const rows: [string, string, string?][] = [
    [text.gross, money(totals.gross, currency), `${totals.charges} charge${totals.charges === 1 ? '' : 's'}`],
    ['Platform commission', money(totals.platform_fee, currency), totals.effective_fee_rate ? percent(totals.effective_fee_rate) : undefined],
    [text.share, money(totals.provider_share, currency)],
  ];
  return (
    <Card data-testid="fee-breakdown">
      <CardHeader>
        <CardTitle>{text.title}</CardTitle>
        <CardDescription>
          {text.description} Last {days} days.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-2 text-sm">
          {rows.map(([label, value, note]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">
                {label}
                {note && <span className="ml-2 text-xs">({note})</span>}
              </dt>
              <dd className="text-right font-mono tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">
          Resources {money(totals.resource_amount, currency)} · tokens {money(totals.token_amount, currency)}. Only READY time and
          successful requests are charged.
        </p>
      </CardContent>
    </Card>
  );
}
