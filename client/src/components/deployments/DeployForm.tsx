'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Notice, TrustNotice } from '@/components/common/Notices';
import { Pill } from '@/components/common/StatusBadge';
import { useCreateDeployment, useQuote } from '@/hooks/useDeployments';
import {
  DEFAULT_NUM_CTX,
  MAX_NUM_CTX,
  MIN_NUM_CTX,
  deployableArtifacts,
  estimateRequirements,
  newIdempotencyKey,
} from '@/lib/deployments';
import { errorMessage, noCapacityDetail, reasonText } from '@/lib/errors';
import { ago, mb, money, runtimeLabel } from '@/lib/format';
import type { Model, Runtime } from '@/types';

export function DeployForm({ model }: { model: Model }) {
  const router = useRouter();
  const create = useCreateDeployment();
  const artifacts = useMemo(() => deployableArtifacts(model.artifacts), [model.artifacts]);
  const [runtime, setRuntime] = useState<Runtime | 'auto'>('auto');
  const [numCtx, setNumCtx] = useState(DEFAULT_NUM_CTX);
  const [requireGpu, setRequireGpu] = useState(false);
  const [region, setRegion] = useState('');
  const [maxHourly, setMaxHourly] = useState('');
  const [maxTokens, setMaxTokens] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  // One key per form instance: a double-submit or retry after a network error returns the same deployment.
  const [idempotencyKey] = useState(newIdempotencyKey);

  const ctxValid = Number.isInteger(numCtx) && numCtx >= MIN_NUM_CTX && numCtx <= MAX_NUM_CTX;
  const shown = runtime === 'auto' ? artifacts : artifacts.filter((a) => a.runtime === runtime);
  const capacity = create.error ? noCapacityDetail(create.error) : null;
  const limitsValid = [maxHourly, maxTokens].every((v) => v.trim() === '' || /^\d+(\.\d{1,8})?$/.test(v.trim()));
  const request = {
    model_id: model.id,
    runtime: runtime === 'auto' ? undefined : runtime,
    config: { num_ctx: numCtx, require_gpu: requireGpu, ...(region.trim() ? { region: region.trim() } : {}) },
    ...(maxHourly.trim() ? { max_hourly_price: maxHourly.trim() } : {}),
    ...(maxTokens.trim() ? { max_token_price: maxTokens.trim() } : {}),
  };
  const quote = useQuote(request, ctxValid && limitsValid && artifacts.length > 0);
  const quoteFor = (rt: string) => quote.data?.by_runtime.find((q) => q.runtime === rt);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!acknowledged || !ctxValid || !limitsValid) return;
    create.mutate(
      { ...request, idempotency_key: idempotencyKey },
      { onSuccess: (dep) => router.push(`/customer/deployments/${dep.id}`) },
    );
  };

  if (artifacts.length === 0) {
    return <Notice tone="danger">This model has no enabled runtime artifact, so it cannot be deployed.</Notice>;
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">Runtime</legend>
        <div className="grid gap-2">
          <RuntimeOption
            checked={runtime === 'auto'}
            onChange={() => setRuntime('auto')}
            title="Automatic"
            detail={`Try ${artifacts.map((a) => runtimeLabel(a.runtime)).join(', then ')} and use the first that fits on a node.`}
          />
          {artifacts.map((a) => (
            <RuntimeOption
              key={a.id}
              checked={runtime === a.runtime}
              onChange={() => setRuntime(a.runtime)}
              title={runtimeLabel(a.runtime)}
              detail={
                <>
                  <span className="font-mono">{a.reference}</span>
                  {a.quantization && <> · {a.quantization}</>}
                  {a.gpu_required && <> · GPU required</>}
                  {' · '}
                  {a.last_ready_at ? `last served successfully ${ago(a.last_ready_at)}` : 'not yet served on AgentMesh'}
                </>
              }
            />
          ))}
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="num_ctx">Context window (tokens)</Label>
          <Input
            id="num_ctx"
            type="number"
            min={MIN_NUM_CTX}
            max={MAX_NUM_CTX}
            step={512}
            value={Number.isNaN(numCtx) ? '' : numCtx}
            onChange={(e) => setNumCtx(e.target.valueAsNumber)}
            aria-invalid={!ctxValid}
          />
          <p className="text-xs text-muted-foreground">
            {MIN_NUM_CTX} to {MAX_NUM_CTX}. Larger windows reserve more memory.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="region">Region (optional)</Label>
          <Input id="region" value={region} maxLength={100} onChange={(e) => setRegion(e.target.value)} placeholder="Any" />
          <p className="text-xs text-muted-foreground">Only nodes whose provider set this exact region are used.</p>
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={requireGpu} onChange={(e) => setRequireGpu(e.target.checked)} />
        Require a GPU
      </label>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">Price limits (optional)</legend>
        <p className="text-xs text-muted-foreground">
          Providers set their own prices. AgentMesh places your deployment on the cheapest machine that fits and never
          on one above your limits, including when it moves after a failure. Leave a limit empty to use the network
          prices as the limit.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="max_hourly_price">Most per hour while ready</Label>
            <Input
              id="max_hourly_price"
              inputMode="decimal"
              value={maxHourly}
              onChange={(e) => setMaxHourly(e.target.value)}
              placeholder={quote.data?.by_runtime[0]?.max_hourly_price ? money(quote.data.by_runtime[0].max_hourly_price, quote.data.currency) : 'Network prices'}
              aria-invalid={!limitsValid}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max_token_price">Most per million tokens</Label>
            <Input
              id="max_token_price"
              inputMode="decimal"
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              placeholder={quote.data?.by_runtime[0]?.max_token_price ? money(quote.data.by_runtime[0].max_token_price, quote.data.currency) : 'Network prices'}
              aria-invalid={!limitsValid}
            />
          </div>
        </div>
      </fieldset>

      <div className="rounded-lg border border-border p-4">
        <p className="mb-2 text-sm font-medium">Resources reserved on the node and price (estimate)</p>
        <ul className="space-y-1 text-sm text-muted-foreground">
          {shown.map((a) => {
            const r = estimateRequirements(a, ctxValid ? numCtx : DEFAULT_NUM_CTX, requireGpu);
            const q = quoteFor(a.runtime);
            const currency = quote.data?.currency;
            return (
              <li key={a.id}>
                <span className="font-medium text-foreground">{runtimeLabel(a.runtime)}:</span> {r.cpu_cores} CPU,{' '}
                {mb(r.ram_mb)} RAM, {mb(r.disk_mb)} disk{r.gpu_required ? `, ${mb(r.vram_mb)} GPU memory` : ''}
                {q && (
                  <span data-testid={`hourly-${a.runtime}`}>
                    {' '}
                    ·{' '}
                    {q.hourly != null && q.cheapest
                      ? Number(q.hourly) === 0 && Number(q.cheapest.input_tokens_per_million) === 0 && Number(q.cheapest.output_tokens_per_million) === 0
                        ? 'free on the cheapest machine'
                        : `${money(q.hourly, currency)} per hour while ready, plus ${money(q.cheapest.input_tokens_per_million, currency)} in / ${money(q.cheapest.output_tokens_per_million, currency)} out per million tokens, on the cheapest of ${q.eligible_nodes} machine${q.eligible_nodes === 1 ? '' : 's'} within your limits`
                      : q.hourly != null
                        ? 'free on the cheapest machine'
                        : q.over_price_limit > 0
                          ? `${q.over_price_limit} machine${q.over_price_limit === 1 ? '' : 's'} fit but charge more than your price limits`
                          : 'no machine can take it right now'}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">
          Figures come from the catalog and live machine prices, and are estimates. You need a wallet balance covering{' '}
          {quote.data?.min_prepaid_hours ?? 1} h of the reservation at the chosen machine&apos;s price to deploy; charges
          are taken from your wallet while the deployment is ready, and never above the prices it was placed at.
        </p>
      </div>

      <TrustNotice />
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={acknowledged}
          onChange={(e) => setAcknowledged(e.target.checked)}
          name="acknowledge"
        />
        I understand the provider can see the prompts and responses this deployment handles.
      </label>

      {create.error && (
        <Notice tone="danger" title={capacity ? 'No node can run this deployment right now' : 'Deployment was not created'}>
          {capacity?.by_runtime ? (
            <ul className="space-y-1">
              {Object.entries(capacity.by_runtime).map(([rt, info]) => (
                <li key={rt}>
                  <span className="font-medium text-foreground">{runtimeLabel(rt)}:</span>{' '}
                  {Object.entries(info.reasons ?? {}).length
                    ? Object.entries(info.reasons ?? {})
                        .map(([reason, n]) => `${n} node${n === 1 ? '' : 's'}: ${reasonText(reason)}`)
                        .join('; ')
                    : info.message}
                </li>
              ))}
            </ul>
          ) : (
            errorMessage(create.error)
          )}
        </Notice>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" size="lg" disabled={!acknowledged || !ctxValid || !limitsValid || create.isPending}>
          {create.isPending ? 'Scheduling…' : 'Deploy'}
        </Button>
        {!acknowledged && <span className="text-xs text-muted-foreground">Confirm the notice above to deploy.</span>}
        {model.license && <Pill>{model.license}</Pill>}
      </div>
    </form>
  );
}

function RuntimeOption({
  checked,
  onChange,
  title,
  detail,
}: {
  checked: boolean;
  onChange: () => void;
  title: string;
  detail: React.ReactNode;
}) {
  return (
    <label
      className={`flex cursor-pointer gap-3 rounded-lg border p-3 text-sm ${checked ? 'border-foreground' : 'border-border'}`}
    >
      <input type="radio" name="runtime" checked={checked} onChange={onChange} className="mt-1" />
      <span>
        <span className="font-medium">{title}</span>
        <span className="block text-xs text-muted-foreground">{detail}</span>
      </span>
    </label>
  );
}
