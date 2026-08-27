'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Bot } from 'lucide-react';

export default function AgentActivityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Agent Activity</h1>
        <p className="text-muted-foreground">Monitor the decisions made by autonomous agents managing your workloads.</p>
      </div>

      <Card className="border-blue-500/20 shadow-none">
        <CardHeader className="bg-blue-500/5 pb-4 border-b border-blue-500/10">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-blue-500" />
            <CardTitle className="text-lg">Agent Orchestrator Log</CardTitle>
          </div>
          <CardDescription>Live stream of agent actions, filtering, scheduling, and error recovery.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="bg-black p-6 font-mono text-sm space-y-4 h-[600px] overflow-y-auto">
             <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">14:32:01</span>
              <span className="text-blue-400 font-bold w-12">INFO</span>
              <span className="text-gray-300">Evaluating deployment constraints for <span className="text-blue-300">dp_8f92a1</span>...</span>
            </div>
            <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">14:32:02</span>
              <span className="text-purple-400 font-bold w-12">SCHED</span>
              <span className="text-gray-300">Selected <span className="text-purple-300">node_4x9b</span> (matches requirements: 24GB VRAM, lat &lt; 50ms)</span>
            </div>
            <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">14:32:05</span>
              <span className="text-green-400 font-bold w-12">EXEC</span>
              <span className="text-gray-300">Deployment successful. Endpoint health checks passing.</span>
            </div>
             <div className="flex gap-4 mt-6 pt-6 border-t border-white/10">
              <span className="text-muted-foreground shrink-0">12:15:44</span>
              <span className="text-yellow-400 font-bold w-12">WARN</span>
              <span className="text-gray-300"><span className="text-yellow-300">node_1a2b</span> missed 3 heartbeats. Marking DEGRADED.</span>
            </div>
            <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">12:15:45</span>
              <span className="text-purple-400 font-bold w-12">SCHED</span>
              <span className="text-gray-300">Initiating autonomous migration of workload <span className="text-blue-300">dp_2c4d5e</span>...</span>
            </div>
            <div className="flex gap-4">
              <span className="text-muted-foreground shrink-0">12:15:48</span>
              <span className="text-green-400 font-bold w-12">EXEC</span>
              <span className="text-gray-300">Migration to <span className="text-purple-300">node_7c1f</span> complete. Workload restored.</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
