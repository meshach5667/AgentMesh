'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorState, Notice, PageHeader } from '@/components/common/Notices';
import { EstimatesTable } from '@/components/billing/EstimatesTable';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { useEstimateSummary, useEstimates } from '@/hooks/useBilling';
import { errorMessage } from '@/lib/errors';
import { money } from '@/lib/format';

export default function CustomerCostsPage() {
  const summary = useEstimateSummary(30);
  const estimates = useEstimates();
  if (summary.isLoading || estimates.isLoading) return <PageSkeleton />;
  const error = summary.error ?? estimates.error;
  if (error) return <ErrorState message={errorMessage(error)} retry={() => (summary.refetch(), estimates.refetch())} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Estimated costs"
        description="What your deployments come to at their providers' published prices. You pay each provider directly; open a deployment to see how."
      />
      <Notice tone="info" title="Estimates, not payments">
        AgentMesh does not charge you, hold your money or record payments. These figures help you and your providers
        agree on what is owed; each provider sets their own terms.
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
                <p className="text-xs text-muted-foreground">
                  {money(t.resource_amount, t.currency)} ready time ({t.ready_hours} h) · {money(t.token_amount, t.currency)} tokens
                </p>
              </CardContent>
            </Card>
          ))
        )}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Recent estimates</CardTitle>
          <CardDescription>One row per deployment, machine and window (newest first).</CardDescription>
        </CardHeader>
        <CardContent>
          <EstimatesTable estimates={estimates.data ?? []} empty="No estimates yet: free machines and deployments that never became ready cost nothing." showDeployment />
        </CardContent>
      </Card>
    </div>
  );
}
