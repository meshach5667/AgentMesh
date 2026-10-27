'use client';

import toast from 'react-hot-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Pill } from '@/components/common/StatusBadge';
import { PriceListForm } from '@/components/pricing/PriceListForm';
import { useNodePricing, useSetNodePricing } from '@/hooks/useNodes';
import { percent } from '@/lib/billing';
import { errorMessage } from '@/lib/errors';
import { dateTime, money } from '@/lib/format';
import { PRICE_FIELDS } from '@/types';

/** A machine's own prices: what it charges, the network prices it is compared to, history, and an editor. */
export function NodePricingCard({ nodeId, editable }: { nodeId: string; editable: boolean }) {
  const { data, isLoading, error } = useNodePricing(nodeId);
  const save = useSetNodePricing(nodeId);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Pricing
          {data && (
            <Pill tone={data.charging?.source === 'node' ? 'green' : 'gray'}>
              {data.charging?.source === 'node' ? 'your prices' : data.charging ? 'network prices' : 'free'}
            </Pill>
          )}
        </CardTitle>
        <CardDescription>
          What customers pay to run on this machine, before the platform commission
          {data ? ` of ${percent(data.commission_rate)}` : ''}. Placement prefers the cheapest machine that fits, and by
          default customers are only placed on machines at or below the network prices.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isLoading && <p className="text-sm text-muted-foreground">Loading prices…</p>}
        {error && <p className="text-sm text-destructive">{errorMessage(error)}</p>}
        {data && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Unit</th>
                    <th className="py-2 pr-4 font-medium">Charging now</th>
                    <th className="py-2 font-medium">Network price</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {PRICE_FIELDS.map(({ key, label, unit }) => (
                    <tr key={key}>
                      <td className="py-2 pr-4">
                        {label} <span className="text-xs text-muted-foreground">{unit}</span>
                      </td>
                      <td className="py-2 pr-4 tabular-nums">{data.charging ? money(data.charging[key], data.currency) : '—'}</td>
                      <td className="py-2 tabular-nums text-muted-foreground">
                        {data.network ? money(data.network[key], data.currency) : 'not set'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {editable && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Set this machine&apos;s prices</p>
                <PriceListForm
                  key={data.history[0]?.id ?? 'none'}
                  idPrefix={`node-${nodeId}`}
                  initial={data.charging}
                  currency={data.currency}
                  commissionRate={data.commission_rate}
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
                  New prices apply at once to new placements. Deployments already on this machine never pay more than
                  the prices they were placed at, so a cut reaches them immediately and a rise does not.
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
                        CPU {money(v.cpu_core_hour, v.currency)}/h · RAM {money(v.ram_gb_hour, v.currency)}/GB-h · tokens{' '}
                        {money(v.input_tokens_per_million, v.currency)}/{money(v.output_tokens_per_million, v.currency)} per M
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
