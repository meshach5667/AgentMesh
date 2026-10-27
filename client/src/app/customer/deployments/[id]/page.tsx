'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { ApiExamples } from '@/components/deployments/ApiExamples';
import { DeploymentTimeline } from '@/components/deployments/DeploymentTimeline';
import { Playground } from '@/components/deployments/Playground';
import { InlineValue } from '@/components/common/CodeBlock';
import { ConfirmButton } from '@/components/common/ConfirmButton';
import { StatusBadge } from '@/components/common/StatusBadge';
import { ErrorState, Notice, PageHeader, TrustNotice } from '@/components/common/Notices';
import { PageSkeleton } from '@/components/ui/Skeleton';
import {
  useDeleteDeployment,
  useDeployment,
  useDeploymentEvents,
  useDeploymentPricing,
  useDeploymentUsage,
  useRestartDeployment,
  useStopDeployment,
} from '@/hooks/useDeployments';
import { useModel } from '@/hooks/useModels';
import { useCharges } from '@/hooks/useBilling';
import { ChargesTable } from '@/components/billing/ChargesTable';
import { sumAmounts } from '@/lib/billing';
import { STATUS_HELP } from '@/lib/deployments';
import { errorMessage } from '@/lib/errors';
import { ago, count, dateTime, money, runtimeLabel, shortId } from '@/lib/format';
import { IN_PROGRESS_STATUSES, TERMINAL_STATUSES, type Deployment, type DeploymentPricing } from '@/types';

export default function DeploymentDetailPage() {
  const id = useParams<{ id: string }>().id;
  const router = useRouter();
  const { data: dep, isLoading, error, refetch } = useDeployment(id);
  const live = !!dep && IN_PROGRESS_STATUSES.includes(dep.status);
  const events = useDeploymentEvents(id, live);
  const usage = useDeploymentUsage(id);
  const model = useModel(dep?.model_id ?? null);
  const charges = useCharges(id);
  const pricing = useDeploymentPricing(id);
  const stop = useStopDeployment();
  const restart = useRestartDeployment();
  const remove = useDeleteDeployment();

  if (isLoading) return <PageSkeleton />;
  if (error || !dep) return <ErrorState message={errorMessage(error, 'Deployment not found')} retry={() => refetch()} />;

  const ended = TERMINAL_STATUSES.includes(dep.status);
  const act = (p: Promise<unknown>, ok: string) => p.then(() => toast.success(ok)).catch((e) => toast.error(errorMessage(e)));

  return (
    <div className="space-y-6">
      <PageHeader
        title={model.data?.name ?? dep.model_tag ?? 'Deployment'}
        description={`Deployment ${dep.id}`}
        actions={
          <>
            {(dep.status === 'READY' || dep.status === 'UNHEALTHY') && (
              <Button variant="outline" disabled={restart.isPending} onClick={() => act(restart.mutateAsync(dep.id), 'Restart requested')}>
                Restart
              </Button>
            )}
            {!ended && dep.status !== 'STOPPING' && (
              <ConfirmButton confirmLabel="Stop deployment" onConfirm={() => act(stop.mutateAsync(dep.id), 'Stop requested')}>
                Stop
              </ConfirmButton>
            )}
            <ConfirmButton
              variant="outline"
              confirmLabel="Delete and revoke its keys"
              onConfirm={() =>
                remove.mutateAsync(dep.id).then(
                  () => {
                    toast.success('Deployment deleted');
                    router.push('/customer/deployments');
                  },
                  (e) => toast.error(errorMessage(e)),
                )
              }
            >
              Delete
            </ConfirmButton>
          </>
        }
      />

      <Card>
        <CardContent className="grid gap-4 pt-6 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Status">
            <StatusBadge status={dep.status} />
          </Field>
          <Field label="Runtime">{runtimeLabel(dep.runtime)}</Field>
          <Field label="Node">
            <span className="font-mono">{shortId(dep.node_id)}</span>
            {dep.schedule_attempts > 1 && <span className="text-muted-foreground"> · attempt {dep.schedule_attempts}</span>}
          </Field>
          <Field label={dep.ready_at ? 'Ready since' : 'Created'}>{dateTime(dep.ready_at ?? dep.created_at)}</Field>
          <Field label="Model reference">
            <span className="break-all font-mono text-xs">{dep.model_tag ?? '—'}</span>
          </Field>
          <Field label="Verified digest">
            <span className="break-all font-mono text-xs">{dep.model_digest ?? 'not yet'}</span>
          </Field>
          <Field label="Context window">{dep.config?.num_ctx?.toLocaleString() ?? '—'} tokens</Field>
          <Field label="Restarts">{dep.restart_count}</Field>
          <Field label="Charged so far">
            <span data-testid="cost-so-far">
              {charges.data ? money(sumAmounts(charges.data), charges.data[0]?.currency) : '—'}
            </span>
          </Field>
        </CardContent>
      </Card>

      <Notice tone={dep.status === 'FAILED' ? 'danger' : dep.status === 'UNHEALTHY' ? 'warning' : 'info'} title={dep.status}>
        {STATUS_HELP[dep.status]}
        {dep.error_message && (
          <span className="mt-1 block">
            <span className="font-mono text-xs">{dep.error_code}</span> {dep.error_message}
          </span>
        )}
      </Notice>

      {dep.status === 'READY' && dep.openai_base_url && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Call this deployment</CardTitle>
              <CardDescription>
                OpenAI-compatible endpoint. Authenticate with an{' '}
                <Link href="/customer/api-keys" className="underline underline-offset-4">
                  API key
                </Link>
                ; a key can be limited to this deployment.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <InlineValue value={dep.openai_base_url} />
              {dep.runtime === 'ollama' && dep.endpoint && (
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Ollama-native API (Ollama deployments only)</p>
                  <InlineValue value={dep.endpoint} />
                </div>
              )}
              <ApiExamples deployment={dep} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Try it</CardTitle>
              <CardDescription>Sends a real request through the gateway. It is metered like any other request.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <TrustNotice />
              <Playground deployment={dep} />
            </CardContent>
          </Card>
        </>
      )}

      <ChargesCard charges={charges} pricing={pricing.data} limits={dep} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Progress</CardTitle>
            <CardDescription>{live ? 'Updating every 2 seconds.' : 'Lifecycle events.'}</CardDescription>
          </CardHeader>
          <CardContent>
            {events.error ? <p className="text-sm text-rose-500">{errorMessage(events.error)}</p> : <DeploymentTimeline events={events.data ?? []} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent requests</CardTitle>
            <CardDescription>Metadata only; prompts and responses are never stored.</CardDescription>
          </CardHeader>
          <CardContent>
            {usage.error ? (
              <p className="text-sm text-rose-500">{errorMessage(usage.error)}</p>
            ) : (usage.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No requests yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Endpoint</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead className="text-right">Tokens in/out</TableHead>
                    <TableHead className="text-right">ms</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(usage.data ?? []).slice(0, 15).map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="text-xs">{ago(u.created_at)}</TableCell>
                      <TableCell className="font-mono text-xs">{u.endpoint}</TableCell>
                      <TableCell className="text-xs">
                        {u.outcome} {u.status_code ? `(${u.status_code})` : ''}
                      </TableCell>
                      <TableCell className="text-right text-xs tabular-nums">
                        {count(u.input_tokens)} / {count(u.output_tokens)}
                      </TableCell>
                      <TableCell className="text-right text-xs tabular-nums">{count(u.duration_ms)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ChargesCard({
  charges,
  pricing,
  limits,
}: {
  charges: ReturnType<typeof useCharges>;
  pricing: DeploymentPricing | undefined;
  limits: Pick<Deployment, 'max_hourly_price' | 'max_token_price'>;
}) {
  const rates = pricing?.rates;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Charges</CardTitle>
        <CardDescription>Rated every few minutes from READY time and runtime-reported tokens.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {pricing && (
          <div className="grid gap-4 rounded-lg border border-border p-4 sm:grid-cols-3" data-testid="deployment-pricing">
            <Field label="Price on its machine now">
              {pricing.placed_at === null
                ? 'Not on a machine right now'
                : pricing.hourly != null && Number(pricing.hourly) > 0
                  ? `${money(pricing.hourly, pricing.currency)} per hour while ready`
                  : 'Free per hour'}
            </Field>
            <Field label="Tokens (per million)">
              {rates
                ? `${money(rates.input_tokens_per_million, pricing.currency)} in · ${money(rates.output_tokens_per_million, pricing.currency)} out`
                : '—'}
            </Field>
            <Field label="Your price limits">
              {limits.max_hourly_price ? `${money(limits.max_hourly_price, pricing.currency)}/h` : 'network prices'}
              {' · '}
              {limits.max_token_price ? `${money(limits.max_token_price, pricing.currency)}/M tokens` : 'network prices'}
            </Field>
            <p className="text-xs text-muted-foreground sm:col-span-3">
              {rates?.source === 'node' ? "The machine's provider set these prices. " : rates ? 'The machine charges the network prices. ' : ''}
              You never pay more than the prices in force when the deployment was placed on this machine; if the provider
              lowers them, you pay the lower price.
            </p>
          </div>
        )}
        <ChargesTable charges={charges.data ?? []} empty="No charges for this deployment yet." />
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="text-sm">{children}</div>
    </div>
  );
}
