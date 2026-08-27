'use client';
import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Activity, Server, Cpu, Zap } from 'lucide-react';

export function LiveStats() {
  const [stats, setStats] = useState({
    activeNodes: 142,
    totalGpus: 324,
    tflops: 12500,
    activeDeployments: 89
  });

  useEffect(() => {
    // Simulate live updates
    const interval = setInterval(() => {
      setStats(prev => ({
        ...prev,
        activeNodes: prev.activeNodes + (Math.random() > 0.8 ? 1 : 0),
        totalGpus: prev.totalGpus + (Math.random() > 0.9 ? 2 : 0),
        tflops: prev.tflops + Math.floor(Math.random() * 50),
      }));
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="py-12 border-y border-border/50 bg-secondary/30">
      <div className="container px-6 mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-8">
          <Card className="p-6 bg-background border-border/50 shadow-none">
            <div className="flex items-center gap-3 mb-2 text-muted-foreground">
              <Server className="w-5 h-5" />
              <span className="text-sm font-medium uppercase tracking-wider">Active Nodes</span>
            </div>
            <div className="text-3xl font-mono font-bold">{stats.activeNodes.toLocaleString()}</div>
          </Card>

          <Card className="p-6 bg-background border-border/50 shadow-none">
            <div className="flex items-center gap-3 mb-2 text-muted-foreground">
              <Cpu className="w-5 h-5" />
              <span className="text-sm font-medium uppercase tracking-wider">Available GPUs</span>
            </div>
            <div className="text-3xl font-mono font-bold">{stats.totalGpus.toLocaleString()}</div>
          </Card>

          <Card className="p-6 bg-background border-border/50 shadow-none">
            <div className="flex items-center gap-3 mb-2 text-muted-foreground">
              <Zap className="w-5 h-5" />
              <span className="text-sm font-medium uppercase tracking-wider">Network TFLOPS</span>
            </div>
            <div className="text-3xl font-mono font-bold">{stats.tflops.toLocaleString()}</div>
          </Card>

          <Card className="p-6 bg-background border-border/50 shadow-none">
            <div className="flex items-center gap-3 mb-2 text-muted-foreground">
              <Activity className="w-5 h-5" />
              <span className="text-sm font-medium uppercase tracking-wider">Live Deployments</span>
            </div>
            <div className="text-3xl font-mono font-bold">{stats.activeDeployments.toLocaleString()}</div>
          </Card>
        </div>
      </div>
    </section>
  );
}
