'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorState, Notice, PageHeader } from '@/components/common/Notices';
import { EstimatesTable } from '@/components/billing/EstimatesTable';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { useEstimateSummary, useEstimates } from '@/hooks/useBilling';
import { errorMessage } from '@/lib/errors';
import { money } from '@/lib/format';

export default function ProviderEstimatesPage() {
  const summary = useEstimateSummary(30);
  const estimates = useEstimates();
  if (summary.isLoading || estimates.isLoading) return <PageSkeleton />;
  const error = summary.error ?? estimates.error;
  if (error) return <ErrorState message={errorMessage(error)} retry={() => (summary.refetch(), estimates.refetch())} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Estimated amounts"
        description="What work on your machines comes to at your published prices, per customer reference. Use it to invoice or reconcile payments you receive directly."
      />
      <Notice tone="info" title="Estimates, not earnings">
        AgentMesh does not collect or pay out money and takes no commission. These are estimates from measured ready
        time and runtime-reported tokens; what you are actually paid is between you and your customers.
      </Notice>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(summary.data?.totals ?? []).length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">Last 30 days</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">Nothing yet</CardContent>
          </Card>
        ) : (
          summary.data!.totals.map((t) => (
            <Card key={t.currency}>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">Last 30 days · {t.currency}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold tabular-nums">{money(t.amount, t.currency)}</p>
                <p className="text-xs text-muted-foreground">{t.ready_hours} h of ready time on your machines</p>
              </CardContent>
            </Card>
          ))
        )}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Recent estimates</CardTitle>
          <CardDescription>
            The customer reference is the one customers see on their deployment and quote when they pay you.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <EstimatesTable estimates={estimates.data ?? []} empty="No priced work on your machines yet." showCustomer showDeployment />
        </CardContent>
      </Card>
    </div>
  );
}
