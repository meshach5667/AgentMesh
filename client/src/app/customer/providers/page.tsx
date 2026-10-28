'use client';

import Link from 'next/link';
import { Cpu, Gauge } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Pill } from '@/components/common/StatusBadge';
import { EmptyState, ErrorState, PageHeader } from '@/components/common/Notices';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { useOffers } from '@/hooks/useProviders';
import { errorMessage } from '@/lib/errors';
import { money, runtimeLabel } from '@/lib/format';
import { PAYMENT_METHOD_LABEL } from '@/types';

/** Compute discovery: providers with machines taking work now, their lowest prices and how they take payment. */
export default function ProvidersPage() {
  const { data, isLoading, error, refetch } = useOffers();
  if (isLoading) return <PageSkeleton />;
  if (error) return <ErrorState message={errorMessage(error)} retry={() => refetch()} />;
  const offers = data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compute providers"
        description="Independent providers with machines that can take work right now. Each sets their own prices and is paid directly by you; AgentMesh charges nothing."
      />
      {offers.length === 0 ? (
        <EmptyState>No provider has a machine taking work right now. Check back soon.</EmptyState>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2" aria-label="Providers">
          {offers.map((o) => (
            <li key={o.id}>
              <Card className="flex h-full flex-col">
                <CardHeader>
                  <CardTitle className="text-base">{o.display_name}</CardTitle>
                  {o.description && <CardDescription>{o.description}</CardDescription>}
                </CardHeader>
                <CardContent className="flex-1 space-y-3 text-sm">
                  <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <Cpu aria-hidden className="size-4" />
                      {o.machines_available} machine{o.machines_available === 1 ? '' : 's'} available
                    </span>
                    {o.gpu_machines > 0 && (
                      <span className="inline-flex items-center gap-1.5">
                        <Gauge aria-hidden className="size-4" />
                        {o.gpu_machines} with GPU
                      </span>
                    )}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Runtimes: </span>
                    {o.runtimes.map(runtimeLabel).join(', ') || '—'}
                  </p>
                  <div>
                    <span className="text-muted-foreground">Prices from: </span>
                    {o.prices.length === 0 && o.free_machines > 0 && 'free'}
                    {o.prices.map((p) => (
                      <span key={p.currency} className="mr-3 inline-block tabular-nums">
                        {money(p.cpu_core_hour ?? 0, p.currency)}/core-h · {money(p.ram_gb_hour ?? 0, p.currency)}/GB-h
                      </span>
                    ))}
                    {o.prices.length > 0 && o.free_machines > 0 && <Pill tone="green">{o.free_machines} free</Pill>}
                  </div>
                  <p>
                    <span className="text-muted-foreground">Payment: </span>
                    {o.accepts_payment_arrangement
                      ? o.payment_methods.map((m) => PAYMENT_METHOD_LABEL[m] ?? m).join(', ') || 'see their arrangement'
                      : 'not published yet'}
                  </p>
                </CardContent>
                <CardFooter className="gap-2">
                  <Link href={`/customer/providers/${o.id}`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>
                    Prices and payment
                  </Link>
                  <Link href={`/customer/models?provider=${o.id}`} className={buttonVariants({ size: 'sm' })}>
                    Deploy on {o.display_name}
                  </Link>
                </CardFooter>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted-foreground">
        Listings are ordered by available capacity and name; sponsorships never affect them or which machine runs your
        deployment.
      </p>
    </div>
  );
}
