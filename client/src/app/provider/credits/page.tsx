'use client';

import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ErrorState, PageHeader } from '@/components/common/Notices';
import { Pill } from '@/components/common/StatusBadge';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { useCredits, useDecideTopup } from '@/hooks/useCredits';
import { errorMessage } from '@/lib/errors';
import { dateTime, money } from '@/lib/format';
import { GATEWAY_LABEL } from '@/types';

export default function ProviderCreditsPage() {
  const credits = useCredits();
  const decide = useDecideTopup();
  if (credits.isLoading) return <PageSkeleton />;
  if (credits.error) return <ErrorState message={errorMessage(credits.error)} retry={() => credits.refetch()} />;
  const { balances, payments } = credits.data!;
  const toConfirm = payments.filter((p) => p.method === 'manual' && p.state === 'PENDING');
  const act = (id: string, accept: boolean) => {
    const reason = accept ? undefined : window.prompt('Why are you rejecting it? (shown to the customer)') ?? undefined;
    if (!accept && reason === undefined) return;
    decide
      .mutateAsync({ id, accept, reason })
      .then(() => toast.success(accept ? 'Confirmed: the customer is credited' : 'Rejected'))
      .catch((e) => toast.error(errorMessage(e)));
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Customer payments"
        description="Credit your customers bought with you. Your priced machines serve a customer only while they hold verified credit; usage draws it down at your prices."
      />
      <Card>
        <CardHeader>
          <CardTitle>Transfers to confirm</CardTitle>
          <CardDescription>
            Confirm only once the money is in your account. Confirming credits the customer at once; it cannot be undone
            here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {toConfirm.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing waiting for you.</p>
          ) : (
            <ul className="divide-y divide-border">
              {toConfirm.map((p) => (
                <li key={p.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                  <span>
                    <span className="font-medium tabular-nums">{money(p.amount, p.currency)}</span> from customer{' '}
                    <span className="font-mono">{p.customer_ref}</span> · reference <span className="font-mono">{p.reference}</span>
                    <span className="block text-xs text-muted-foreground">
                      {dateTime(p.created_at)}
                      {p.note ? ` · ${p.note}` : ''}
                    </span>
                  </span>
                  <span className="flex gap-2">
                    <Button size="sm" disabled={decide.isPending} onClick={() => act(p.id, true)}>
                      I received it
                    </Button>
                    <Button size="sm" variant="outline" disabled={decide.isPending} onClick={() => act(p.id, false)}>
                      Not received
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Customer balances</CardTitle>
        </CardHeader>
        <CardContent>
          {balances.length === 0 ? (
            <p className="text-sm text-muted-foreground">No customer holds credit with you yet.</p>
          ) : (
            <ul className="divide-y divide-border text-sm">
              {balances.map((b) => (
                <li key={`${b.customer_ref}-${b.currency}`} className="flex justify-between py-2">
                  <span className="font-mono">{b.customer_ref}</span>
                  <span className="tabular-nums">{money(b.balance, b.currency)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>All payments</CardTitle>
        </CardHeader>
        <CardContent>
          {payments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No payments yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Customer</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>Reference</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payments.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="text-xs">{dateTime(p.created_at)}</TableCell>
                      <TableCell className="font-mono text-xs">{p.customer_ref}</TableCell>
                      <TableCell className="text-xs">{p.gateway ? GATEWAY_LABEL[p.gateway] : 'Transfer'}</TableCell>
                      <TableCell className="font-mono text-xs">{p.reference}</TableCell>
                      <TableCell className="text-right tabular-nums">{money(p.amount, p.currency)}</TableCell>
                      <TableCell>
                        <Pill tone={p.state === 'VERIFIED' ? 'green' : p.state === 'PENDING' || p.state === 'REVIEW' ? 'amber' : 'red'}>{p.state.toLowerCase()}</Pill>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
