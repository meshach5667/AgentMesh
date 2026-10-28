'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorState, PageHeader } from '@/components/common/Notices';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { PaymentArrangement } from '@/components/providers/PaymentArrangement';
import { useProvider } from '@/hooks/useProviders';
import { errorMessage } from '@/lib/errors';
import { money, runtimeLabel } from '@/lib/format';
import { PRICE_FIELDS } from '@/types';

export default function ProviderDetailPage() {
  const id = useParams<{ id: string }>().id;
  const { data: p, isLoading, error, refetch } = useProvider(id);
  if (isLoading) return <PageSkeleton />;
  if (error || !p) return <ErrorState message={errorMessage(error, 'Provider not found')} retry={() => refetch()} />;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title={p.display_name}
        description={p.description ?? 'Independent compute provider on AgentMesh.'}
        actions={
          <Link href={`/customer/models?provider=${p.id}`} className={buttonVariants()}>
            Deploy on {p.display_name}
          </Link>
        }
      />
      <Card>
        <CardHeader>
          <CardTitle>Capacity and prices</CardTitle>
          <CardDescription>
            {p.machines_available} machine{p.machines_available === 1 ? '' : 's'} taking work now
            {p.gpu_machines > 0 ? `, ${p.gpu_machines} with a GPU` : ''}. Runtimes:{' '}
            {p.runtimes.map(runtimeLabel).join(', ') || '—'}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {p.prices.length === 0 ? (
            <p className="text-muted-foreground">{p.free_machines > 0 ? 'Its available machines are free to use.' : 'No prices published.'}</p>
          ) : (
            p.prices.map((price) => (
              <div key={price.currency}>
                <p className="mb-1 text-xs text-muted-foreground">Lowest prices in {price.currency}</p>
                <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
                  {PRICE_FIELDS.map(({ key, label, unit }) => (
                    <div key={key} className="flex justify-between gap-4 border-b border-border py-1">
                      <dt className="text-muted-foreground">
                        {label} <span className="text-xs">{unit}</span>
                      </dt>
                      <dd className="tabular-nums">{money(price[key] ?? 0, price.currency)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))
          )}
          <p className="text-xs text-muted-foreground">
            Each machine has its own price list; the deploy form shows the exact price of the machine your deployment
            would get.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>How to pay {p.display_name}</CardTitle>
        </CardHeader>
        <CardContent>
          <PaymentArrangement payment={p.payment} providerName={p.display_name} />
        </CardContent>
      </Card>
    </div>
  );
}
