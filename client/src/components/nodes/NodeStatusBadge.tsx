import React from 'react';
import { Badge } from '../ui/badge';
import type { NodeStatus, DeploymentStatus } from '../../types';

export function NodeStatusBadge({
  status,
}: {
  status: NodeStatus | DeploymentStatus | string;
}) {
  const variantMap: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
    ONLINE: 'default',
    AVAILABLE: 'default',
    RUNNING: 'default',
    BUSY: 'secondary',
    DEPLOYING: 'secondary',
    OFFLINE: 'destructive',
    STOPPED: 'destructive',
    REGISTERING: 'secondary',
    SCHEDULING: 'secondary',
    DEGRADED: 'destructive',
    FAILED: 'destructive',
  };
  return <Badge variant={variantMap[status] || 'default'}>{status}</Badge>;
}
