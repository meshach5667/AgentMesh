'use client';

import React from 'react';
import { useNodes } from '@/hooks/useNodes';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Server, Activity, Plus, RefreshCw } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ExtendedNode } from '@/types';

export default function ProviderNodesPage() {
  const { data: nodes, isLoading, error, refetch } = useNodes();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'AVAILABLE': return 'bg-green-500/10 text-green-500 hover:bg-green-500/20';
      case 'BUSY': return 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20';
      case 'OFFLINE': return 'bg-red-500/10 text-red-500 hover:bg-red-500/20';
      default: return 'bg-gray-500/10 text-gray-400 hover:bg-gray-500/20';
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading node registry...</div>;
  }

  if (error) {
    return <div className="p-8 text-center text-destructive">Failed to load nodes. Please try again.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Network Nodes</h1>
          <p className="text-muted-foreground">Manage your compute infrastructure connected to AgentMesh.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button>
            <Plus className="mr-2 h-4 w-4" /> Register Node
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Nodes</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{nodes?.length || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Compute</CardTitle>
            <Activity className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {nodes?.filter(n => n.status === 'AVAILABLE' || n.status === 'BUSY').length || 0}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Hardware Registry</CardTitle>
          <CardDescription>Real-time telemetry and resource allocation across your nodes.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Node ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Hardware</TableHead>
                <TableHead>Utilization</TableHead>
                <TableHead>Pricing</TableHead>
                <TableHead className="text-right">Last Heartbeat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nodes?.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    No nodes registered. Install the AgentMesh Node Agent to connect compute.
                  </TableCell>
                </TableRow>
              ) : (
                nodes?.map((node: ExtendedNode) => (
                  <TableRow key={node.id}>
                    <TableCell className="font-mono text-sm">{node.id.substring(0, 8)}...</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={getStatusColor(node.status)}>
                        {node.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm font-medium">{node.hardware?.gpu_model || 'CPU Only'}</div>
                      <div className="text-xs text-muted-foreground">
                        {node.hardware?.gpu_vram_gb ? `${Math.round(node.hardware.gpu_vram_gb / (1024 ** 3))} GB VRAM` : `${Math.round((node.hardware?.ram_gb || 0) / (1024 ** 3))} GB RAM`}
                      </div>
                    </TableCell>
                    <TableCell className="w-[200px]">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span>GPU</span>
                          <span className="font-mono text-muted-foreground">{node.metrics?.gpu_utilization_percent || 0}%</span>
                        </div>
                        <Progress value={node.metrics?.gpu_utilization_percent || 0} className="h-1" />
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      ${node.pricing?.gpu_hour_price?.toFixed(2) || '0.00'}/hr
                    </TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">
                      {node.last_heartbeat ? formatDistanceToNow(new Date(node.last_heartbeat), { addSuffix: true }) : 'Never'}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
