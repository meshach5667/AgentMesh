import React from 'react';
import { Badge } from '../ui/Badge';
import type { NodeStatus } from '../../types';

export function NodeStatusBadge({ status }: { status: NodeStatus }) {
  const variantMap: Record<string, any> = {
    ONLINE: 'success', AVAILABLE: 'success', RUNNING: 'success',
    BUSY: 'warning', DEPLOYING: 'warning',
    OFFLINE: 'error', STOPPED: 'error',
    REGISTERING: 'info', SCHEDULING: 'info',
    DEGRADED: 'warning', FAILED: 'error'
  };
  return <Badge variant={variantMap[status] || 'default'}>{status}</Badge>;
}
