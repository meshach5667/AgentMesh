'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { PageHeader } from '@/components/common/Notices';
import { RevenueView } from '@/components/billing/RevenueView';
import { useRevenue } from '@/hooks/useBilling';
import { money } from '@/lib/format';

function MoneyFlows() {
  const { data } = useRevenue(30, 'network');
  if (!data) return null;
  const t = data.totals;
  const rows: [string, string | undefined, string][] = [
    ['Customer top-ups (Paystack)', t.topups, 'Money in'],
    ['Provider payouts sent', t.payouts, 'Money out'],
    ['Top-ups refunded to cards', t.card_refunds, 'Money out'],
    ['Charges refunded to wallets', t.refunded, 'Of which commission given up: ' + money(t.fee_reversed, data.currency)],
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Money movement</CardTitle>
        <CardDescription>Last 30 days. Wallet top-ups and payouts are not revenue; they are shown to reconcile cash.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-2 text-sm">
          {rows.map(([label, value, note]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">
                {label} <span className="text-xs">({note})</span>
              </dt>
              <dd className="text-right font-mono tabular-nums">{money(value ?? 0, data.currency)}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

export default function OperatorRevenuePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Revenue"
        description="Compute commission is the primary revenue: the platform's share of every rated charge, net of refunds. Sponsorships are reported separately as supplementary revenue."
      />
      <RevenueView scope="network" />
      <MoneyFlows />
    </div>
  );
}
