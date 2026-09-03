'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Wallet, CreditCard, Activity } from 'lucide-react';
import { useWallet } from '@/hooks/useWallet';
import { PageSkeleton } from '@/components/ui/Skeleton';

export default function CustomerWalletPage() {
  const { data: wallet, isLoading } = useWallet();

  if (isLoading) {
    return <PageSkeleton />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Wallet</h1>
        <p className="text-muted-foreground">Manage your compute credits for deploying AI models.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-blue-500/30 shadow-lg shadow-blue-500/5">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Available Balance</CardTitle>
            <Wallet className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold mb-4">${wallet?.balance?.toFixed(2) || '150.00'}</div>
            <div className="flex gap-3">
              <Button className="w-full bg-blue-600 hover:bg-blue-700 text-white">
                <CreditCard className="mr-2 h-4 w-4" /> Add Funds
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Current Spend Rate</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-400">-$0.45 / hr</div>
            <p className="text-xs text-muted-foreground mt-1">Based on 2 active deployments</p>
            <div className="mt-4 pt-4 border-t border-border/50 flex justify-between items-center text-sm">
              <span className="text-muted-foreground">Estimated runway:</span>
              <span className="font-medium">~14 days</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Payment Methods</CardTitle>
          <CardDescription>Configure how you fund your AI workloads.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 border border-border rounded-lg bg-secondary/20">
             <div className="flex items-center gap-4">
                <div className="w-10 h-6 bg-white rounded flex items-center justify-center">
                  <span className="text-[10px] font-bold text-blue-800">VISA</span>
                </div>
                <div>
                  <p className="text-sm font-medium">Visa ending in 4242</p>
                  <p className="text-xs text-muted-foreground">Expires 12/25</p>
                </div>
             </div>
             <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20">Default</Badge>
          </div>
          <Button variant="outline" className="w-full border-dashed">
            + Add Payment Method
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
