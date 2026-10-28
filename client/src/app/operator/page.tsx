'use client';

import { Activity, Box, MessageSquare, Server } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatCard } from '@/components/common/StatCard';
import { StatusBadge } from '@/components/common/StatusBadge';
import { ErrorState, Notice, PageHeader } from '@/components/common/Notices';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { useOperatorOverview } from '@/hooks/useAdmin';
import { errorMessage } from '@/lib/errors';
import { count, dateTime, runtimeLabel } from '@/lib/format';

const sum = (o: Record<string, number>, keys?: string[]) =>
  Object.entries(o).reduce((t, [k, v]) => (!keys || keys.includes(k) ? t + v : t), 0);

export default function OperatorOverview() {
  const { data, isLoading, error, refetch } = useOperatorOverview();
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState message={errorMessage(error)} retry={() => refetch()} />;

  const healthy = sum(data.nodes_by_health, ['ACTIVE', 'BUSY']);
  const rec = data.recovery_24h;
  const u = data.usage_24h;

  return (
    <div className="space-y-6">
      <PageHeader title="Network overview" description={`Live from the database · ${dateTime(data.generated_at)}`} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Healthy nodes"
          value={`${healthy} / ${sum(data.nodes_by_health)}`}
          hint={`${data.nodes_by_health.DEGRADED ?? 0} degraded · ${data.nodes_by_health.OFFLINE ?? 0} offline`}
          icon={Server}
        />
        <StatCard
          title="Deployments ready"
          value={data.deployments_by_status.READY ?? 0}
          hint={Object.entries(data.deployments_by_runtime).map(([r, n]) => `${runtimeLabel(r)} ${n}`).join(' · ') || undefined}
          icon={Activity}
        />
        <StatCard
          title="Requests (24 h)"
          value={count(u.requests)}
          hint={`${count(u.failed)} failed · ${count(u.output_tokens)} output tokens`}
          icon={MessageSquare}
        />
        <StatCard title="Deployable models" value={data.models.deployable} hint={`${data.models.approved} approved of ${data.models.total}`} icon={Box} />
      </div>

      {data.nodes_heartbeat_overdue > 0 && (
        <Notice tone="warning" title="Heartbeats overdue">
          {data.nodes_heartbeat_overdue} node(s) are marked online but have not reported within the heartbeat timeout. The
          health monitor will mark them offline and move their deployments; if this persists, check that the monitor is
          running (it needs the leader lock when several replicas run).
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <BreakdownCard title="Nodes by health" data={data.nodes_by_health} badges />
        <BreakdownCard title="Deployments by status" data={data.deployments_by_status} badges />
        <BreakdownCard title="Users by role" data={data.users_by_role} />
      </div>

      {(rec.needs_attention > 0 || rec.waiting_for_node > 0) && (
        <Notice tone="warning" title="Deployments waiting for a node">
          {rec.waiting_for_node} waiting and retrying automatically; {rec.needs_attention} waiting for their customer (manual
          failover policy, or only dearer nodes available).
        </Notice>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Failover in the last 24 hours</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm sm:grid-cols-3">
          <div>
            <p className="text-xs text-muted-foreground">Deployments moved to another node</p>
            <p className="text-2xl font-semibold tabular-nums">{rec.moves}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Attempts ended</p>
            <ul className="mt-1 space-y-0.5">
              {Object.keys(rec.attempts_ended).length === 0 ? (
                <li className="text-muted-foreground">none</li>
              ) : (
                Object.entries(rec.attempts_ended).map(([outcome, n]) => (
                  <li key={outcome} className="flex justify-between gap-4">
                    <span>{outcome.replace(/_/g, ' ')}</span>
                    <span className="tabular-nums">{n}</span>
                  </li>
                ))
              )}
            </ul>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Waiting now</p>
            <p className="tabular-nums">
              {rec.waiting_for_node} retrying · {rec.needs_attention} need their customer
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function BreakdownCard({ title, data, badges }: { title: string; data: Record<string, number>; badges?: boolean }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">None.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {entries.map(([k, n]) => (
              <li key={k} className="flex items-center justify-between">
                {badges ? <StatusBadge status={k} /> : <span className="capitalize">{k}</span>}
                <span className="tabular-nums">{n}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
