'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState, ErrorState, Notice, PageHeader } from '@/components/common/Notices';
import { RefundsTable } from '@/components/billing/RefundsTable';
import { TableSkeleton } from '@/components/ui/Skeleton';
import { useAdminRefunds, useAdminTopups, useCharges, useIssueRefund, usePaymentsConfig, type RefundInput } from '@/hooks/useBilling';
import { errorMessage } from '@/lib/errors';
import { dateTime, money, shortId } from '@/lib/format';

/** Inline refund form: amount (empty = everything that is left) and a reason the customer will see. */
function RefundForm({ target, max, currency, onDone }: { target: Omit<RefundInput, 'reason' | 'amount'>; max: string; currency: string; onDone: () => void }) {
  const issue = useIssueRefund();
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  return (
    <form
      className="flex flex-wrap items-end gap-2 rounded-lg border border-border bg-muted/30 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        issue.mutate(
          { ...target, amount: amount || undefined, reason: reason.trim() },
          {
            onSuccess: (r) => {
              if (r.status === 'FAILED') toast.error(`Refund failed: ${r.failure_reason ?? 'unknown reason'}`);
              else toast.success(r.status === 'PENDING' ? 'Refund sent to Paystack; funds are held until it completes' : `Refunded ${money(r.amount, r.currency)}`);
              onDone();
            },
            onError: (err) => toast.error(errorMessage(err)),
          },
        );
      }}
    >
      <div className="space-y-1">
        <label htmlFor="refund-amount" className="text-xs text-muted-foreground">
          Amount ({currency})
        </label>
        <Input id="refund-amount" type="number" min={0} max={max} step="any" placeholder={`All: ${max}`} value={amount} onChange={(e) => setAmount(e.target.value)} className="w-36" />
      </div>
      <div className="min-w-56 flex-1 space-y-1">
        <label htmlFor="refund-reason" className="text-xs text-muted-foreground">
          Reason (shown to the customer)
        </label>
        <Input id="refund-reason" required minLength={3} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <Button type="submit" size="sm" variant="destructive" disabled={issue.isPending}>
        {target.kind === 'charge' ? 'Refund to wallet' : 'Refund to card'}
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={onDone}>
        Cancel
      </Button>
    </form>
  );
}

export default function OperatorRefundsPage() {
  const config = usePaymentsConfig();
  const charges = useCharges();
  const [email, setEmail] = useState('');
  const [search, setSearch] = useState('');
  const topups = useAdminTopups(search);
  const refunds = useAdminRefunds();
  const [open, setOpen] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Refunds"
        description="Refund a compute charge to the customer's wallet (the provider's share and the commission are reversed in the same proportions), or send unspent wallet funds back to the customer's card through Paystack. Every refund is audited and reconciled."
      />

      <Card>
        <CardHeader>
          <CardTitle>Compute charges</CardTitle>
          <CardDescription>Most recent first. A provider whose share was already paid out goes negative; later earnings cover it.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {charges.error ? (
            <ErrorState message={errorMessage(charges.error)} />
          ) : charges.isLoading ? (
            <TableSkeleton />
          ) : (charges.data ?? []).length === 0 ? (
            <EmptyState>No charges yet.</EmptyState>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Period</TableHead>
                  <TableHead>Deployment</TableHead>
                  <TableHead className="text-right">Charged</TableHead>
                  <TableHead className="text-right">Refunded</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(charges.data ?? []).map((c) => {
                  const left = Number(c.amount) - Number(c.refunded_amount);
                  return (
                    <TableRow key={c.id}>
                      <TableCell className="text-xs">{dateTime(c.period_start)}</TableCell>
                      <TableCell className="font-mono text-xs">{shortId(c.deployment_id)}</TableCell>
                      <TableCell className="text-right font-mono text-xs">{money(c.amount, c.currency)}</TableCell>
                      <TableCell className="text-right font-mono text-xs">{money(c.refunded_amount, c.currency)}</TableCell>
                      <TableCell className="text-right">
                        {open === c.id ? null : (
                          <Button size="sm" variant="outline" disabled={left <= 0} onClick={() => setOpen(c.id)}>
                            {left <= 0 ? 'Refunded' : 'Refund'}
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
          {open && charges.data?.some((c) => c.id === open) && (() => {
            const c = charges.data.find((x) => x.id === open)!;
            return (
              <RefundForm
                target={{ id: c.id, kind: 'charge' }}
                max={(Number(c.amount) - Number(c.refunded_amount)).toFixed(8).replace(/\.?0+$/, '')}
                currency={c.currency}
                onDone={() => setOpen(null)}
              />
            );
          })()}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Top-ups</CardTitle>
          <CardDescription>Successful Paystack top-ups. Only money still in the customer&apos;s wallet can go back to their card.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!config.data?.enabled && <Notice title="Payments are not configured">Card refunds need Paystack.</Notice>}
          <form
            className="flex max-w-md gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setSearch(email.trim());
            }}
          >
            <Input type="email" placeholder="Customer email" aria-label="Customer email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Button type="submit" variant="outline" size="sm">
              Search
            </Button>
          </form>
          {topups.error ? (
            <ErrorState message={errorMessage(topups.error)} />
          ) : (topups.data ?? []).length === 0 ? (
            <EmptyState>No successful top-ups{search ? ` for ${search}` : ''}.</EmptyState>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Paid</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead className="text-right">Refundable</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(topups.data ?? []).map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="text-xs">{dateTime(p.paid_at ?? p.created_at)}</TableCell>
                    <TableCell className="text-sm">{p.user_email ?? '—'}</TableCell>
                    <TableCell className="font-mono text-xs">{p.reference}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{money(p.amount, p.currency)}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{money(p.refundable, p.currency)}</TableCell>
                    <TableCell className="text-right">
                      {open !== p.id && (
                        <Button size="sm" variant="outline" disabled={!config.data?.enabled || Number(p.refundable) <= 0} onClick={() => setOpen(p.id)}>
                          Refund
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {open && topups.data?.some((p) => p.id === open) && (() => {
            const p = topups.data.find((x) => x.id === open)!;
            return <RefundForm target={{ id: p.id, kind: 'topup' }} max={p.refundable} currency={p.currency} onDone={() => setOpen(null)} />;
          })()}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Refund history</CardTitle>
        </CardHeader>
        <CardContent>
          {refunds.error ? <ErrorState message={errorMessage(refunds.error)} /> : <RefundsTable refunds={refunds.data ?? []} showSplit empty="No refunds yet." />}
        </CardContent>
      </Card>
    </div>
  );
}
