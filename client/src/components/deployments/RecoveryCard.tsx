'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Pill } from '@/components/common/StatusBadge';
import { useDeploymentAttempts, useRetryDeployment, useUpdateDeployment } from '@/hooks/useDeployments';
import { errorMessage } from '@/lib/errors';
import { dateTime, money } from '@/lib/format';
import { TERMINAL_STATUSES, WAITING_STATUSES, type Deployment, type FailoverPolicy } from '@/types';

const OUTCOME: Record<string, { text: string; tone: 'red' | 'amber' | 'gray' }> = {
  node_failed: { text: 'Node failed', tone: 'red' },
  workload_failed: { text: 'Workload failed', tone: 'red' },
  stopped: { text: 'Stopped', tone: 'gray' },
  superseded: { text: 'Replaced without interruption', tone: 'gray' },
  cancelled: { text: 'Move cancelled', tone: 'amber' },
};

export const POLICY_TEXT: Record<FailoverPolicy, { label: string; help: string }> = {
  any_provider: {
    label: 'Move to any eligible provider',
    help: 'If its node fails, AgentMesh restarts it on the cheapest suitable machine, which may belong to another provider.',
  },
  same_provider: {
    label: 'Only this provider’s machines',
    help: 'If its node fails, it moves only to another machine of the same provider (who already sees its data).',
  },
  manual: {
    label: 'Ask me first',
    help: 'If its node fails, it is not moved automatically: it waits for you to retry.',
  },
};

/** Placement history and recovery controls: every attempt, why it ended, and what happens next. */
export function RecoveryCard({ dep }: { dep: Deployment }) {
  const attempts = useDeploymentAttempts(dep.id);
  const update = useUpdateDeployment(dep.id);
  const retry = useRetryDeployment(dep.id);
  const waiting = WAITING_STATUSES.includes(dep.status);
  const ended = TERMINAL_STATUSES.includes(dep.status);
  const [maxHourly, setMaxHourly] = useState(dep.max_hourly_price ?? '');
  const [maxTokens, setMaxTokens] = useState(dep.max_token_price ?? '');
  const limitsValid = [maxHourly, maxTokens].every((v) => v.trim() === '' || /^\d+(\.\d{1,8})?$/.test(v.trim()));
  const currency = dep.currency ?? 'NGN';
  const moved = (attempts.data?.length ?? 0) > 1;

  const saveLimits = () =>
    update
      .mutateAsync({
        max_hourly_price: maxHourly.trim() || null,
        max_token_price: maxTokens.trim() || null,
      })
      .then(() => toast.success('Price limits saved'))
      .catch((e) => toast.error(errorMessage(e)));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Placement and recovery {moved && <Pill tone="amber">recovered by moving</Pill>}
        </CardTitle>
        <CardDescription>
          When a node fails, AgentMesh restarts the deployment on another suitable node from its model source. This is
          a restart, not a live migration: requests in flight on the failed node are lost and can be retried.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {dep.migrating_node_id && (
          <p role="status" className="rounded-md border border-brand/25 bg-brand-soft p-3 text-sm">
            Moving to another machine without interruption: the replacement is starting while the current machine keeps
            serving. Traffic switches the moment it is ready
            {dep.migration_started_at ? ` (started ${dateTime(dep.migration_started_at)})` : ''}.
          </p>
        )}
        {dep.status === 'PENDING' && (
          <p role="status" className="rounded-md border border-amber-500/30 bg-amber-500/[0.06] p-3 text-sm">
            Waiting for a suitable node. Next automatic try {dep.next_placement_at ? `at ${dateTime(dep.next_placement_at)}` : 'soon'}
            {dep.placement_retries > 0 ? ` (retried ${dep.placement_retries} time${dep.placement_retries === 1 ? '' : 's'} so far)` : ''}.
          </p>
        )}
        {dep.status === 'NEEDS_ATTENTION' && (
          <p role="alert" className="rounded-md border border-rose-500/30 bg-rose-500/[0.06] p-3 text-sm">
            {dep.error_code === 'PRICE_APPROVAL_REQUIRED'
              ? 'Only machines that cost more than its previous placement are available. Raise your price limit below to approve a higher price, then retry.'
              : dep.error_code === 'CREDIT_EXHAUSTED'
                ? 'Paused: it needs prepaid credit with the provider of a suitable machine. Buy credit under Prepaid credit; it restarts automatically once the payment is verified.'
                : 'Automatic recovery is off for this deployment. Retry when you are ready.'}
          </p>
        )}

        <div>
          <p className="mb-2 text-sm font-medium">Attempts</p>
          {attempts.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {attempts.error && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(attempts.error)}
            </p>
          )}
          {attempts.data && attempts.data.length === 0 && <p className="text-sm text-muted-foreground">Not placed on a node yet.</p>}
          {attempts.data && attempts.data.length > 0 && (
            <ol className="space-y-2">
              {attempts.data.map((a) => (
                <li key={a.id} className="rounded-md border border-border p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">Attempt {a.number}</span>
                    {a.provider && <span className="text-muted-foreground">on {a.provider}</span>}
                    {a.active ? (
                      <Pill tone={a.state === 'running' ? 'green' : 'blue'}>{a.state === 'running' ? 'serving' : 'starting'}</Pill>
                    ) : (
                      a.outcome && <Pill tone={OUTCOME[a.outcome]?.tone ?? 'gray'}>{OUTCOME[a.outcome]?.text ?? a.outcome}</Pill>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Assigned {dateTime(a.assigned_at)}
                    {a.ready_at && <> · served from {dateTime(a.ready_at)}</>}
                    {a.ended_at && <> · ended {dateTime(a.ended_at)}</>}
                  </p>
                  {a.error_message && (
                    <p className="mt-1 text-xs">
                      <span className="font-mono">{a.error_code}</span> {a.error_message}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>

        {!ended && (
          <div className="grid gap-4 border-t border-border pt-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="failover-policy">If its node fails</Label>
              <select
                id="failover-policy"
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={dep.failover_policy}
                disabled={update.isPending}
                onChange={(e) =>
                  update
                    .mutateAsync({ failover_policy: e.target.value as FailoverPolicy })
                    .then(() => toast.success('Failover policy saved'))
                    .catch((err) => toast.error(errorMessage(err)))
                }
              >
                {(Object.keys(POLICY_TEXT) as FailoverPolicy[]).map((p) => (
                  <option key={p} value={p}>
                    {POLICY_TEXT[p].label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">{POLICY_TEXT[dep.failover_policy]?.help}</p>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Price limits ({currency})</p>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label htmlFor="rc-max-hourly" className="text-xs font-normal text-muted-foreground">
                    Most per hour
                  </Label>
                  <Input id="rc-max-hourly" inputMode="decimal" value={maxHourly} placeholder="No limit" onChange={(e) => setMaxHourly(e.target.value)} aria-invalid={!limitsValid} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="rc-max-tokens" className="text-xs font-normal text-muted-foreground">
                    Most per million tokens
                  </Label>
                  <Input id="rc-max-tokens" inputMode="decimal" value={maxTokens} placeholder="No limit" onChange={(e) => setMaxTokens(e.target.value)} aria-invalid={!limitsValid} />
                </div>
              </div>
              {!limitsValid && <p className="text-xs text-destructive">Use numbers such as 12 or 0.5.</p>}
              <p className="text-xs text-muted-foreground">
                Without a limit, a move never costs more than the placement it replaces
                {dep.max_hourly_price ? ` (now at most ${money(dep.max_hourly_price, currency)} per hour)` : ''}.
              </p>
              <Button size="sm" variant="outline" disabled={!limitsValid || update.isPending} onClick={saveLimits}>
                Save limits
              </Button>
            </div>
          </div>
        )}

        {waiting && (
          <Button
            disabled={retry.isPending}
            onClick={() =>
              retry
                .mutateAsync()
                .then((d) => toast[d.status === 'SCHEDULED' ? 'success' : 'error'](d.status === 'SCHEDULED' ? 'Placed on a node' : 'Still no suitable node'))
                .catch((e) => toast.error(errorMessage(e)))
            }
          >
            {retry.isPending ? 'Looking for a node…' : 'Retry placement now'}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
