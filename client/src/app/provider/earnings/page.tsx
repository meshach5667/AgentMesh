'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DollarSign, ArrowUpRight, Wallet, History } from 'lucide-react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useEarnings, usePayoutHistory } from '@/hooks/useEarnings';

export default function EarningsPage() {
  const { data: earnings, isLoading: earningsLoading } = useEarnings();
  const { data: history, isLoading: historyLoading } = usePayoutHistory();

  const pending = earnings?.pending_earnings || 0;
  const available = earnings?.available_balance || 0;
  const total = earnings?.total_earned || 0;

  if (earningsLoading) {
     return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading earnings...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Earnings</h1>
        <p className="text-muted-foreground">Track your compute revenue and manage payouts.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Earnings</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${pending.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground mt-1">Accumulated since last payout</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Available Balance</CardTitle>
            <Wallet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex justify-between items-end">
              <div>
                <div className="text-2xl font-bold">${available.toFixed(2)}</div>
                <p className="text-xs text-muted-foreground mt-1">Ready for withdrawal</p>
              </div>
              <Button size="sm" disabled={available <= 0}>Withdraw</Button>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Earned</CardTitle>
            <ArrowUpRight className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${total.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground mt-1">All time revenue</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <History className="w-5 h-5" />
            <CardTitle>Payout History</CardTitle>
          </div>
          <CardDescription>Recent settlements to your configured payout method.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {historyLoading ? (
                 <TableRow>
                  <TableCell colSpan={4} className="text-center py-4 text-muted-foreground">Loading history...</TableCell>
                </TableRow>
              ) : history?.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-4 text-muted-foreground">No payout history found.</TableCell>
                </TableRow>
              ) : history?.map((record) => (
                <TableRow key={record.id}>
                  <TableCell>{record.date}</TableCell>
                  <TableCell>{record.type}</TableCell>
                  <TableCell>
                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold bg-green-500/10 text-green-500 border-green-500/20">
                      {record.status}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono font-medium text-green-500">
                    +${record.amount.toFixed(2)}
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
