'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Activity } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export default function CustomerTransactionsPage() {
  const transactions = [
    { id: 'tx_c1', date: '2024-03-10 14:32', type: 'Compute Deduction', deployment: 'dep-llama-1', amount: 1.25, status: 'Settled' },
    { id: 'tx_c2', date: '2024-03-10 12:15', type: 'Compute Deduction', deployment: 'dep-mistral-2', amount: 0.85, status: 'Settled' },
    { id: 'tx_c3', date: '2024-03-09 10:00', type: 'Deposit', deployment: '-', amount: 50.00, status: 'Completed' },
    { id: 'tx_c4', date: '2024-03-08 18:20', type: 'Compute Deduction', deployment: 'dep-llama-1', amount: 0.45, status: 'Settled' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Transaction History</h1>
        <p className="text-muted-foreground">Review your deposits and compute spending.</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5" />
            <CardTitle>Recent Activity</CardTitle>
          </div>
          <CardDescription>Real-time ledger of your network usage and payments.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Transaction ID</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Deployment</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.map((tx) => (
                <TableRow key={tx.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{tx.id}</TableCell>
                  <TableCell className="text-sm">{tx.date}</TableCell>
                  <TableCell className="text-sm">{tx.type}</TableCell>
                  <TableCell className="text-sm font-mono">{tx.deployment}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20">
                      {tx.status}
                    </Badge>
                  </TableCell>
                  <TableCell className={`text-right font-mono ${tx.type === 'Deposit' ? 'text-green-500' : 'text-foreground'}`}>
                    {tx.type === 'Deposit' ? '+' : '-'}${tx.amount.toFixed(2)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
