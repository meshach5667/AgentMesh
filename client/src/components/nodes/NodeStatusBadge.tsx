'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { NodeStatus, DeploymentStatus } from '../../types';

interface NodeStatusBadgeProps {
  status: NodeStatus | DeploymentStatus | string;
  showDot?: boolean;
  className?: string;
}

export function NodeStatusBadge({
  status,
  showDot = true,
  className,
}: NodeStatusBadgeProps) {
  const getStatusConfig = (s: string) => {
    switch (s) {
      case 'ONLINE':
      case 'AVAILABLE':
      case 'RUNNING':
        return {
          wrapper: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25 dark:bg-emerald-500/15',
          dot: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]',
          ping: 'bg-emerald-400',
          label: s,
        };
      case 'BUSY':
      case 'DEPLOYING':
      case 'SCHEDULING':
      case 'REGISTERING':
        return {
          wrapper: 'bg-blue-500/10 text-blue-400 border-blue-500/25 dark:bg-blue-500/15',
          dot: 'bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.8)]',
          ping: 'bg-blue-400',
          label: s,
        };
      case 'OFFLINE':
      case 'STOPPED':
      case 'DEGRADED':
      case 'FAILED':
        return {
          wrapper: 'bg-rose-500/10 text-rose-400 border-rose-500/25 dark:bg-rose-500/15',
          dot: 'bg-rose-400',
          ping: 'bg-rose-400',
          label: s,
        };
      default:
        return {
          wrapper: 'bg-muted text-muted-foreground border-border',
          dot: 'bg-muted-foreground',
          ping: 'bg-muted-foreground',
          label: s,
        };
    }
  };

  const config = getStatusConfig(status);

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono border transition-colors shadow-sm',
        config.wrapper,
        className
      )}
    >
      {showDot && (
        <span className="relative flex h-2 w-2">
          {status !== 'OFFLINE' && status !== 'STOPPED' && (
            <span
              className={cn(
                'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
                config.ping
              )}
            />
          )}
          <span className={cn('relative inline-flex rounded-full h-2 w-2', config.dot)} />
        </span>
      )}
      <span>{config.label}</span>
    </span>
  );
}
