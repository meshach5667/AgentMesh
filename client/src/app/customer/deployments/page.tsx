'use client';

import React from 'react';
import { useDeployments } from '@/hooks/useDeployments';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { RefreshCw, Play, Square, Activity, Bot, } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { Deployment } from '@/types';

export default function CustomerDeploymentsPage() {
  const { data: deployments, isLoading, refetch } = useDeployments();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'RUNNING': return 'bg-green-500/10 text-green-500 border-green-500/20';
      case 'DEPLOYING': return 'bg-blue-500/10 text-blue-500 border-blue-500/20 animate-pulse';
      case 'STOPPED': return 'bg-gray-500/10 text-gray-500 border-gray-500/20';
      case 'FAILED': return 'bg-red-500/10 text-red-500 border-red-500/20';
      default: return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20';
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading deployments...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Active Workloads</h1>
          <p className="text-muted-foreground">Manage your AI model deployments on the AgentMesh network.</p>
        </div>
        <Button variant="outline" size="icon" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Deployments</CardTitle>
              <CardDescription>All running and stopped model endpoints.</CardDescription>
            </div>
            <Badge variant="outline" className="bg-secondary/50">
              {deployments?.length || 0} Total Workloads
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Deployment ID</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Assigned Node</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deployments?.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    No active deployments. Head to the Model Catalog to deploy a model.
                  </TableCell>
                </TableRow>
              ) : (
                deployments?.map((deployment: Deployment) => (
                  <TableRow key={deployment.id}>
                    <TableCell className="font-mono text-xs">{deployment.id.substring(0, 12)}...</TableCell>
                    <TableCell className="font-medium">{deployment.model_id}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={getStatusColor(deployment.status)}>
                        {deployment.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {deployment.node_id ? deployment.node_id.substring(0,8) + '...' : 'Unassigned'}
                    </TableCell>
                    <TableCell className="text-sm">
                      {deployment.created_at ? formatDistanceToNow(new Date(deployment.created_at)) : 'N/A'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {deployment.status === 'RUNNING' ? (
                          <Button variant="ghost" size="icon" className="text-red-500 hover:text-red-600 hover:bg-red-500/10">
                            <Square className="h-4 w-4" />
                          </Button>
                        ) : (
                          <Button variant="ghost" size="icon" className="text-green-500 hover:text-green-600 hover:bg-green-500/10">
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        <Button variant="ghost" size="icon">
                          <Activity className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="border-blue-500/20 shadow-none">
        <CardHeader className="bg-blue-500/5 pb-4 border-b border-blue-500/10">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-blue-500" />
            <CardTitle className="text-lg">Agent Orchestrator Log</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="bg-black/50 p-4 font-mono text-xs space-y-2 h-[200px] overflow-y-auto">
             <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">14:32:01</span>
              <span className="text-blue-400">INFO</span>
              <span className="text-gray-300">Evaluating deployment constraints for dp_8f92a1...</span>
            </div>
            <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">14:32:02</span>
              <span className="text-purple-400">SCHED</span>
              <span className="text-gray-300">Selected node_4x9b (matches requirements: 24GB VRAM, lat &lt; 50ms)</span>
            </div>
            <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">14:32:05</span>
              <span className="text-green-400">EXEC</span>
              <span className="text-gray-300">Deployment successful. Endpoint health checks passing.</span>
            </div>
             <div className="flex gap-4 mt-2 pt-2 border-t border-white/5">
              <span className="text-muted-foreground shrink-0">12:15:44</span>
              <span className="text-yellow-400">WARN</span>
              <span className="text-gray-300">node_1a2b missed 3 heartbeats. Marking DEGRADED.</span>
            </div>
            <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">12:15:45</span>
              <span className="text-purple-400">SCHED</span>
              <span className="text-gray-300">Initiating autonomous migration of workload dp_2c4d5e...</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
