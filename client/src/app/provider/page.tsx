'use client';

import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { EarningsChart } from '../../components/charts/EarningsChart';
import { Server, Activity, DollarSign, ActivityIcon } from 'lucide-react';
import { useNodes } from '@/hooks/useNodes';
import { useDeployments } from '@/hooks/useDeployments';
import { useEarnings } from '@/hooks/useEarnings';
import { PageSkeleton } from '@/components/ui/Skeleton';

export default function ProviderDashboard() {
  const { data: nodes, isLoading: nodesLoading } = useNodes();
  const { data: deployments, isLoading: deploymentsLoading } = useDeployments();
  const { data: earnings, isLoading: earningsLoading } = useEarnings();

  const isLoading = nodesLoading || deploymentsLoading || earningsLoading;

  if (isLoading) return <PageSkeleton />;

  const totalNodes = nodes?.length || 0;
  const onlineNodes = nodes?.filter(n => n.status === 'AVAILABLE' || n.status === 'BUSY' || n.status === 'ONLINE').length || 0;
  const activeDeployments = deployments?.filter(d => d.status === 'READY').length || 0;
  const totalEarned = earnings?.total_earned || 0;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
      <p className="text-muted-foreground">High-level view of your compute infrastructure and earnings.</p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Nodes</CardTitle>
                <Server className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-bold">{totalNodes}</div>
            </CardContent>
        </Card>
        <Card className="border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Online Nodes</CardTitle>
                <Activity className="w-4 h-4 text-green-500" />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-bold text-green-500">{onlineNodes}</div>
            </CardContent>
        </Card>
        <Card className="border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Active Deployments</CardTitle>
                <ActivityIcon className="w-4 h-4 text-blue-500" />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-bold text-blue-500">{activeDeployments}</div>
            </CardContent>
        </Card>
        <Card className="border-border">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Earnings</CardTitle>
                <DollarSign className="w-4 h-4 text-green-500" />
            </CardHeader>
            <CardContent>
                <div className="text-3xl font-bold text-green-500">${Number(totalEarned).toFixed(2)}</div>
            </CardContent>
        </Card>
      </div>
      <Card className="border-border">
        <CardHeader><CardTitle>Earnings History</CardTitle></CardHeader>
        <CardContent>
          <EarningsChart data={[{date: 'Mon', amount: 40}, {date: 'Tue', amount: 60}, {date: 'Wed', amount: 45}]} />
        </CardContent>
      </Card>
    </div>
  );
}
