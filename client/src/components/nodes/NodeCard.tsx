'use client';

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { NodeStatusBadge } from './NodeStatusBadge';
import { Cpu, HardDrive, Zap, MapPin, Gauge } from 'lucide-react';
import type { Node } from '../../types';

export function NodeCard({ node }: { node: Node }) {
  return (
    <Card className="border-border/60 bg-card/60 backdrop-blur-md hover:border-blue-500/40 hover:shadow-lg hover:shadow-blue-500/5 transition-all duration-300">
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div className="space-y-1">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            {node.name}
          </CardTitle>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
            <MapPin className="h-3 w-3 text-muted-foreground/70" />
            <span>{node.region || 'Global'}</span>
          </div>
        </div>
        <NodeStatusBadge status={node.status} />
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="p-2.5 rounded-lg border border-border/50 bg-secondary/30">
            <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
              <span>GPU Unit</span>
            </div>
            <p className="font-semibold text-foreground truncate">
              {node.hardware?.gpu_model || 'CPU Only'}
            </p>
            {node.hardware?.gpu_vram_gb && (
              <p className="text-[10px] text-muted-foreground font-mono">
                {Math.round(node.hardware.gpu_vram_gb / (1024 ** 3))} GB VRAM
              </p>
            )}
          </div>

          <div className="p-2.5 rounded-lg border border-border/50 bg-secondary/30">
            <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
              <Cpu className="h-3.5 w-3.5 text-blue-400" />
              <span>CPU Cores</span>
            </div>
            <p className="font-semibold text-foreground truncate">
              {node.hardware?.cpu_model || 'vCPU'}
            </p>
            <p className="text-[10px] text-muted-foreground font-mono">
              {node.hardware?.cpu_cores || 0} Cores • {Math.round((node.hardware?.ram_gb || 0) / (1024 ** 3))} GB
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-border/40 text-xs">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Gauge className="h-3.5 w-3.5 text-emerald-400" />
            <span>Reputation</span>
          </div>
          <span className="font-mono font-bold text-foreground">
            {node.reputation_score || 100}/100
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
