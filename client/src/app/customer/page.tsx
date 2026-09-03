'use client';

import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { formatCurrency } from '../../lib/utils';
import { Activity, CreditCard, DollarSign } from 'lucide-react';
import { useDeployments } from '@/hooks/useDeployments';
import { useWallet } from '@/hooks/useWallet';
import { PageSkeleton } from '@/components/ui/Skeleton';

export default function CustomerDashboard() {
  const { data: deployments, isLoading: deploymentsLoading } = useDeployments();
  const { data: wallet, isLoading: walletLoading } = useWallet();

  if (deploymentsLoading || walletLoading) return <PageSkeleton />;

  const activeDeployments = deployments?.filter(d => d.status === 'RUNNING').length || 0;
  const totalDeployments = deployments?.length || 0;
  const balance = wallet?.balance || 0;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
      <p className="text-muted-foreground">High-level view of your AI deployments and compute spending.</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Active Deployments</CardTitle>
                <Activity className="w-4 h-4 text-blue-500" />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-bold text-blue-500">{activeDeployments}</div>
                <p className="text-xs text-muted-foreground mt-1">{totalDeployments} total</p>
            </CardContent>
        </Card>
        <Card className="border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Deployments</CardTitle>
                <DollarSign className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-bold text-foreground">{totalDeployments}</div>
            </CardContent>
        </Card>
        <Card className="border-border border-blue-500/30 bg-blue-500/5">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Wallet Balance</CardTitle>
                <CreditCard className="w-4 h-4 text-blue-500" />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-bold text-foreground">{formatCurrency(Number(balance))}</div>
            </CardContent>
        </Card>
      </div>
    </div>
  );
}
