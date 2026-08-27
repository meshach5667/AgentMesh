import React from 'react';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../ui/table';
import { Badge } from '../ui/badge';
import { formatCurrency, formatDate } from '../../lib/utils';
import type { Transaction } from '../../types';

export function TransactionList({ transactions }: { transactions: Transaction[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Amount</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {transactions.map(t => (
          <TableRow key={t.id}>
            <TableCell>{formatDate(t.created_at)}</TableCell>
            <TableCell>{t.type}</TableCell>
            <TableCell>{formatCurrency(t.amount)}</TableCell>
            <TableCell><Badge>{t.status}</Badge></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
