'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ErrorState } from '@/components/common/Notices';
import { TableSkeleton } from '@/components/ui/Skeleton';
import { LedgerTable, TYPE_LABEL } from '@/components/wallet/LedgerTable';
import { downloadLedgerCsv, useTransactions } from '@/hooks/useTransactions';
import { useWallet } from '@/hooks/useWallet';
import { errorMessage } from '@/lib/errors';
import type { TransactionType } from '@/types';

const PAGE = 100;

/** The caller's ledger, filterable by entry type, paged, and downloadable as CSV. */
export function LedgerHistory({ types }: { types: TransactionType[] }) {
  const [type, setType] = useState<TransactionType | ''>('');
  const [page, setPage] = useState(0);
  const filter = { types: type ? [type] : undefined, limit: PAGE, offset: page * PAGE };
  const tx = useTransactions(filter);
  const wallet = useWallet();
  const rows = tx.data ?? [];
  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="ledger-type" className="text-sm text-muted-foreground">
            Type
          </label>
          <select
            id="ledger-type"
            value={type}
            onChange={(e) => {
              setType(e.target.value as TransactionType | '');
              setPage(0);
            }}
            className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
          >
            <option value="">All</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {TYPE_LABEL[t]}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            onClick={() => downloadLedgerCsv({ types: type ? [type] : undefined }).catch((e) => toast.error(errorMessage(e)))}
          >
            <Download className="size-3.5" /> Export CSV
          </Button>
        </div>
        {tx.error ? (
          <ErrorState message={errorMessage(tx.error)} retry={() => tx.refetch()} />
        ) : tx.isLoading ? (
          <TableSkeleton />
        ) : (
          <LedgerTable rows={rows} walletId={wallet.data?.id} empty={type ? 'No entries of this type.' : 'No transactions yet.'} />
        )}
        {(page > 0 || rows.length === PAGE) && (
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Newer
            </Button>
            <Button size="sm" variant="ghost" disabled={rows.length < PAGE} onClick={() => setPage(page + 1)}>
              Older
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
