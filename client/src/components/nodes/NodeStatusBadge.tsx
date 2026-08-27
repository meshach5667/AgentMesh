import React from 'react';
import { Badge, type BadgeProps } from '../ui/Badge';
import type { NodeStatus, DeploymentStatus } from '../../types';

export function NodeStatusBadge({
  status,
}: {
  status: NodeStatus | DeploymentStatus | string;
}) {
  const variantMap: Record<string, BadgeProps['variant']> = {
    ONLINE: 'success',
    AVAILABLE: 'success',
    RUNNING: 'success',
    BUSY: 'warning',
    DEPLOYING: 'warning',
    OFFLINE: 'error',
    STOPPED: 'error',
    REGISTERING: 'info',
    SCHEDULING: 'info',
    DEGRADED: 'warning',
    FAILED: 'error',
  };
  return <Badge variant={variantMap[status] || 'default'}>{status}</Badge>;
}
