'use client';

import { SponsoredSlot } from '@/components/sponsorship/SponsoredSlot';
import Link from 'next/link';
import { Calculator, HeartPulse, MessageSquare, Server } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatCard } from '@/components/common/StatCard';
import { EmptyState, ErrorState, Notice, PageHeader } from '@/components/common/Notices';
import { NodeTable } from '@/components/nodes/NodeTable';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { useEstimateSummary } from '@/hooks/useBilling';
import { useMyProviderProfile } from '@/hooks/useProviders';
import { useNodes } from '@/hooks/useNodes';
import { useUsageSummary } from '@/hooks/useUsage';
import { errorMessage } from '@/lib/errors';
import { count, money } from '@/lib/format';
import { safeExternalUrl } from '@/lib/billing';
import { nodeAvailability } from '@/lib/nodes';
import type { PaymentProfile } from '@/types';

function hasArrangement(p: PaymentProfile | null): boolean {
  return !!p && (p.methods.length > 0 || !!p.instructions || p.links.some((l) => safeExternalUrl(l.url)));
}

export default function ProviderOverview() {
  const nodes = useNodes();
  const estimates = useEstimateSummary(30);
  const profile = useMyProviderProfile();
  const usage = useUsageSummary(7);

  if (nodes.isLoading) return <PageSkeleton />;
  if (nodes.error) return <ErrorState message={errorMessage(nodes.error)} retry={() => nodes.refetch()} />;

  const list = (nodes.data ?? []).filter((n) => n.status !== 'REVOKED');
  const accepting = list.filter((n) => nodeAvailability(n).tone === 'green').length;
  const attention = list.filter((n) => nodeAvailability(n).tone === 'red');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Your machines on AgentMesh and the work they serve."
        actions={
          <Link href="/provider/nodes/register" className={buttonVariants()}>
            Add a machine
          </Link>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Nodes accepting work" value={`${accepting} / ${list.length}`} icon={Server} />
        <StatCard
          title="Healthy machines"
          value={`${list.filter((n) => n.health === 'ACTIVE' || n.health === 'BUSY').length} / ${list.length}`}
          hint={`${list.filter((n) => n.health === 'BUSY').length} running work`}
          icon={HeartPulse}
        />
        <StatCard
          title="Requests served (7 days)"
          value={usage.data ? count(usage.data.totals.requests) : '—'}
          hint={usage.data ? `${count(usage.data.totals.output_tokens)} output tokens` : undefined}
          icon={MessageSquare}
        />
        <StatCard
          title="Estimated due (30 days)"
          value={
            estimates.data
              ? estimates.data.totals.length
                ? estimates.data.totals.map((t) => money(t.amount, t.currency)).join(' + ')
                : 'nothing yet'
              : '—'
          }
          hint="At your prices; customers pay you directly"
          icon={Calculator}
        />
      </div>
      {profile.data && !hasArrangement(profile.data.payment) && (
        <Notice tone="warning" title="Customers cannot see how to pay you">
          Publish your payment arrangement so customers on your priced machines know how to pay you.{' '}
          <Link href="/provider/payments" className="underline underline-offset-4">
            Set it up
          </Link>
        </Notice>
      )}
      {attention.length > 0 && (
        <Notice tone="warning" title={`${attention.length} node${attention.length === 1 ? ' needs' : 's need'} attention`}>
          {attention.map((n) => `${n.name ?? n.id.slice(0, 8)}: ${nodeAvailability(n).detail}`).join(' ')}
        </Notice>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Nodes</CardTitle>
        </CardHeader>
        <CardContent>
          {list.length === 0 ? (
            <EmptyState action={{ href: '/provider/nodes/register', label: 'Enroll your first machine' }}>
              You have no nodes yet.
            </EmptyState>
          ) : (
            <NodeTable nodes={list} href={(n) => `/provider/nodes/${n.id}`} />
          )}
        </CardContent>
      </Card>
      <SponsoredSlot placement="provider_dashboard" className="max-w-xl" />
    </div>
  );
}
