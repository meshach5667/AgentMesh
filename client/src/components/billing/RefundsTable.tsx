import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { StatusBadge } from '@/components/common/StatusBadge';
import { EmptyState } from '@/components/common/Notices';
import { dateTime, money } from '@/lib/format';
import type { Refund } from '@/types';

export function RefundsTable({ refunds, empty, showSplit = false }: { refunds: Refund[]; empty: string; showSplit?: boolean }) {
  if (refunds.length === 0) return <EmptyState>{empty}</EmptyState>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead>Kind</TableHead>
          <TableHead>Reason</TableHead>
          <TableHead>Status</TableHead>
          {showSplit && <TableHead className="text-right">From provider / commission</TableHead>}
          <TableHead className="text-right">Amount</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {refunds.map((r) => (
          <TableRow key={r.id} data-testid="refund-row">
            <TableCell className="text-xs">{dateTime(r.created_at)}</TableCell>
            <TableCell className="text-sm">{r.kind === 'charge' ? 'Charge, to wallet' : 'Top-up, to card'}</TableCell>
            <TableCell className="max-w-xs truncate text-sm text-muted-foreground" title={r.reason}>
              {r.reason}
            </TableCell>
            <TableCell>
              <StatusBadge status={r.status} />
              {r.failure_reason && <div className="text-xs text-muted-foreground">{r.failure_reason}</div>}
            </TableCell>
            {showSplit && (
              <TableCell className="text-right font-mono text-xs">
                {r.kind === 'charge' ? `${money(r.provider_amount, r.currency)} / ${money(r.platform_fee, r.currency)}` : '—'}
              </TableCell>
            )}
            <TableCell className="text-right font-mono text-xs">{money(r.amount, r.currency)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
