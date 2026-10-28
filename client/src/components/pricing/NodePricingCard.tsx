'use client';

import toast from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Pill } from '@/components/common/StatusBadge';
import { PriceListForm } from '@/components/pricing/PriceListForm';
import { useNodePricing, useSetNodePricing } from '@/hooks/useNodes';
import { isFree } from '@/lib/billing';
import { errorMessage } from '@/lib/errors';
import { dateTime, money } from '@/lib/format';
import { PRICE_FIELDS } from '@/types';

/** A machine's own prices: what it charges, history, and an editor. */
export function NodePricingCard({ nodeId, editable }: { nodeId: string; editable: boolean }) {
  const { data, isLoading, error } = useNodePricing(nodeId);
  const save = useSetNodePricing(nodeId);
  const free = !data?.charging || isFree(data.charging);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Pricing {data && <Pill tone={free ? 'gray' : 'green'}>{free ? 'free' : data.charging?.currency}</Pill>}
        </CardTitle>
        <CardDescription>
          What customers pay you to run on this machine. Placement prefers the cheapest machine that fits a
          customer&apos;s limits, so your price affects how often it is chosen.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isLoading && <p className="text-sm text-muted-foreground">Loading prices…</p>}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(error)}
          </p>
        )}
        {data && (
          <>
            {free ? (
              <p className="text-sm text-muted-foreground">This machine is free to use: it has no prices of its own.</p>
            ) : (
              <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                {PRICE_FIELDS.map(({ key, label, unit }) => (
                  <div key={key} className="flex justify-between gap-4 border-b border-border py-1.5">
                    <dt className="text-muted-foreground">
                      {label} <span className="text-xs">{unit}</span>
                    </dt>
                    <dd className="tabular-nums">{money(data.charging![key], data.charging!.currency)}</dd>
                  </div>
                ))}
              </dl>
            )}

            {editable && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Set this machine&apos;s prices</p>
                <PriceListForm
                  key={data.history[0]?.id ?? 'none'}
                  idPrefix={`node-${nodeId}`}
                  initial={data.charging}
                  submitLabel="Publish prices"
                  pending={save.isPending}
                  onSubmit={(prices) =>
                    save
                      .mutateAsync(prices)
                      .then(() => toast.success('Prices published'))
                      .catch((e) => toast.error(errorMessage(e)))
                  }
                />
                <p className="text-xs text-muted-foreground">
                  New prices apply at once to new placements. Deployments already on this machine are never estimated
                  above the prices they were placed at, so a cut reaches them immediately and a rise does not.
                </p>
              </div>
            )}

            {data.history.length > 0 && (
              <div>
                <p className="mb-2 text-sm font-medium">History</p>
                <ul className="divide-y divide-border text-sm">
                  {data.history.map((v) => (
                    <li key={v.id} className="flex flex-wrap justify-between gap-2 py-2">
                      <span>
                        Version {v.version} <span className="text-muted-foreground">· {dateTime(v.effective_from)}</span>
                      </span>
                      <span className="text-xs tabular-nums text-muted-foreground">
                        CPU {money(v.cpu_core_hour, v.currency)}/h · RAM {money(v.ram_gb_hour, v.currency)}/GB-h · GPU{' '}
                        {money(v.vram_gb_hour, v.currency)}/GB-h · tokens {money(v.input_tokens_per_million, v.currency)} in /{' '}
                        {money(v.output_tokens_per_million, v.currency)} out per M
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
