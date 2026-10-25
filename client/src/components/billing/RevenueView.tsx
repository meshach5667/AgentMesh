'use client';

import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { StatCard } from '@/components/common/StatCard';
import { EmptyState, ErrorState } from '@/components/common/Notices';
import { TableSkeleton } from '@/components/ui/Skeleton';
import { useRevenue } from '@/hooks/useBilling';
import { errorMessage } from '@/lib/errors';
import { money } from '@/lib/format';
import type { BillingScope, RevenueAnalytics } from '@/types';

const DAY_OPTIONS = [7, 30, 90];

const SERIES = [
  { key: 'provider_share', color: 'var(--viz-provider)' },
  { key: 'platform_fee', color: 'var(--viz-commission)' },
] as const;

const LABELS: Record<BillingScope, { provider_share: string; platform_fee: string; title: string; description: string }> = {
  customer: {
    title: 'Spending per day',
    description: 'What your deployments were charged each day, split into the provider’s share and the platform commission.',
    provider_share: 'Paid to providers',
    platform_fee: 'Platform commission',
  },
  provider: {
    title: 'Earnings per day',
    description: 'What customers paid for deployments on your nodes each day: your share, and the platform commission.',
    provider_share: 'Your share',
    platform_fee: 'Platform commission',
  },
  network: {
    title: 'Compute revenue per day',
    description: 'Rated compute charges on the whole network: provider earnings and platform commission.',
    provider_share: 'Provider earnings',
    platform_fee: 'Platform commission',
  },
};

function tiles(data: RevenueAnalytics) {
  const t = data.totals;
  const c = data.currency;
  if (data.scope === 'customer')
    return [
      ['Charged', money(t.gross, c), `Includes ${money(t.platform_fee, c)} platform commission`],
      ['Refunded to you', money(t.refunded, c), 'Credited back to your wallet'],
      ['Net spend', money(t.net_customer_spend, c), 'Charged minus refunds'],
    ];
  if (data.scope === 'provider')
    return [
      ['Customers paid', money(t.gross, c), `${money(t.platform_fee, c)} kept as platform commission`],
      ['Your net earnings', money(t.net_provider_earnings, c), 'Your share minus refunded charges'],
      ['Taken back for refunds', money(t.clawback, c), 'Your share of refunded charges'],
    ];
  return [
    ['Customer charges', money(t.gross, c), `${money(t.refunded, c)} refunded`],
    ['Platform commission (net)', money(t.net_platform_commission, c), 'Primary revenue: commission minus refunds'],
    ['Sponsorships', money(t.sponsorship ?? 0, c), 'Supplementary revenue from sponsored placements'],
    ['Platform revenue', money(t.platform_revenue ?? 0, c), `Providers earned ${money(t.net_provider_earnings, c)}`],
  ];
}

interface TooltipProps {
  active?: boolean;
  payload?: readonly { dataKey?: unknown; value?: unknown; color?: string }[];
  label?: unknown;
  currency: string;
  labels: Record<string, string>;
}

function ChartTooltip({ active, payload, label, currency, labels }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((sum, p) => sum + Number(p.value ?? 0), 0);
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-sm">
      <p className="mb-1 font-medium">{String(label)}</p>
      {[...payload].reverse().map((p) => (
        <p key={String(p.dataKey)} className="flex items-center gap-2">
          <span className="inline-block size-2 rounded-sm" style={{ background: p.color }} aria-hidden />
          <span className="text-muted-foreground">{labels[String(p.dataKey)]}</span>
          <span className="ml-auto font-mono tabular-nums">{money(Number(p.value ?? 0), currency)}</span>
        </p>
      ))}
      <p className="mt-1 flex justify-between border-t border-border pt-1">
        <span className="text-muted-foreground">Charged</span>
        <span className="font-mono tabular-nums">{money(total, currency)}</span>
      </p>
    </div>
  );
}

/** Revenue analytics for one scope: totals, a daily stacked chart (with a table view), and the biggest contributors. */
export function RevenueView({ scope }: { scope?: BillingScope }) {
  const [days, setDays] = useState(30);
  const [asTable, setAsTable] = useState(false);
  const { data, isLoading, error, refetch } = useRevenue(days, scope);

  if (error) return <ErrorState message={errorMessage(error)} retry={() => refetch()} />;
  if (isLoading || !data) return <TableSkeleton rows={3} />;
  const labels = LABELS[data.scope];
  const points = data.series.map((p) => ({ date: p.date.slice(5), provider_share: Number(p.provider_share), platform_fee: Number(p.platform_fee) }));
  const anything = points.some((p) => p.provider_share || p.platform_fee);
  const breakdownName = { deployment: 'Deployment', node: 'Node', provider: 'Provider' }[data.breakdown_by];

  return (
    <div className="space-y-6" data-testid="revenue-view">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Period</span>
        {DAY_OPTIONS.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => setDays(d)}
            aria-pressed={d === days}
            className={`rounded-md border px-2.5 py-1 ${d === days ? 'border-foreground font-medium' : 'border-border text-muted-foreground'}`}
          >
            {d} days
          </button>
        ))}
      </div>
      <div className={`grid gap-4 sm:grid-cols-2 ${data.scope === 'network' ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
        {tiles(data).map(([title, value, hint]) => (
          <StatCard key={title} title={title} value={value} hint={hint} />
        ))}
      </div>
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1.5">
            <CardTitle>{labels.title}</CardTitle>
            <CardDescription>{labels.description}</CardDescription>
          </div>
          <button type="button" className="shrink-0 text-xs text-muted-foreground underline underline-offset-4" onClick={() => setAsTable(!asTable)}>
            {asTable ? 'Show chart' : 'Show table'}
          </button>
        </CardHeader>
        <CardContent>
          {!anything ? (
            <EmptyState>No charges in the last {days} days.</EmptyState>
          ) : asTable ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Charged</TableHead>
                  <TableHead className="text-right">{labels.provider_share}</TableHead>
                  <TableHead className="text-right">{labels.platform_fee}</TableHead>
                  <TableHead className="text-right">Refunded</TableHead>
                  {data.scope === 'network' && <TableHead className="text-right">Sponsorships</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.series
                  .filter((p) => Number(p.gross) || Number(p.refunded) || Number(p.sponsorship ?? 0))
                  .map((p) => (
                    <TableRow key={p.date}>
                      <TableCell className="text-xs">{p.date}</TableCell>
                      {[p.gross, p.provider_share, p.platform_fee, p.refunded, ...(data.scope === 'network' ? [p.sponsorship ?? '0'] : [])].map((v, i) => (
                        <TableCell key={i} className="text-right font-mono text-xs">
                          {money(v, data.currency)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          ) : (
            <>
              <div className="mb-3 flex gap-4 text-xs text-muted-foreground" aria-label="Legend">
                {SERIES.map((s) => (
                  <span key={s.key} className="flex items-center gap-1.5">
                    <span className="inline-block size-2.5 rounded-sm" style={{ background: s.color }} aria-hidden />
                    {labels[s.key]}
                  </span>
                ))}
              </div>
              <div className="h-64 w-full" data-testid="revenue-chart" role="img" aria-label={`${labels.title}, ${labels.provider_share} and ${labels.platform_fee}`}>
                <ResponsiveContainer>
                  <BarChart data={points} barCategoryGap="20%">
                    <CartesianGrid vertical={false} className="stroke-border" strokeOpacity={0.6} />
                    <XAxis dataKey="date" fontSize={11} tickLine={false} axisLine={false} minTickGap={16} className="fill-muted-foreground" />
                    <YAxis fontSize={11} tickLine={false} axisLine={false} width={64} tickFormatter={(v) => money(v, data.currency).replace(/\.\d+$/, '')} />
                    <Tooltip cursor={{ className: 'fill-muted', opacity: 0.4 }} content={({ active, payload, label }) => (
                        <ChartTooltip active={active} payload={payload} label={label} currency={data.currency} labels={labels} />
                      )} />
                    {SERIES.map((s, i) => (
                      <Bar
                        key={s.key}
                        dataKey={s.key}
                        stackId="charge"
                        fill={s.color}
                        stroke="var(--card)"
                        strokeWidth={2}
                        radius={i === SERIES.length - 1 ? [4, 4, 0, 0] : 0}
                        isAnimationActive={false}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </CardContent>
      </Card>
      {data.breakdown.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>By {breakdownName.toLowerCase()}</CardTitle>
            <CardDescription>Largest first, last {days} days.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{breakdownName}</TableHead>
                  <TableHead className="text-right">Charges</TableHead>
                  <TableHead className="text-right">Charged</TableHead>
                  <TableHead className="text-right">{labels.platform_fee}</TableHead>
                  <TableHead className="text-right">{labels.provider_share}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.breakdown.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell className="text-sm">{b.label}</TableCell>
                    <TableCell className="text-right tabular-nums">{b.charges}</TableCell>
                    {[b.gross, b.platform_fee, b.provider_share].map((v, i) => (
                      <TableCell key={i} className="text-right font-mono text-xs">
                        {money(v, data.currency)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
