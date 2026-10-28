import { parseApiDate } from './format';
import type { Node } from '@/types';

export type NodeAvailability = { label: string; tone: 'green' | 'amber' | 'red' | 'gray'; detail: string };

const WORKER_REASON: Record<string, string> = {
  paused: 'paused on the machine (agentmesh-worker pause)',
  draining: 'draining on the machine (agentmesh-worker drain)',
  schedule: 'outside the availability schedule set on the machine',
};

/**
 * Whether new deployments can be placed on the node, and why not. Uses the control plane's own health verdict
 * (``health``/``schedulable``, derived from heartbeats, recovery, failure cooldown and pauses) when present, so the
 * dashboard never claims a node is healthy merely because it exists.
 */
export function nodeAvailability(node: Node, heartbeatTimeoutSeconds = 90): NodeAvailability {
  if (node.status === 'REVOKED') return { label: 'Revoked', tone: 'red', detail: 'Its credential no longer works. Enroll the machine again to reuse it.' };
  if (node.status === 'SUSPENDED') return { label: 'Suspended', tone: 'red', detail: 'Suspended by an operator.' };
  if (node.status === 'QUARANTINED') return { label: 'Quarantined', tone: 'red', detail: 'Cut off by an operator pending investigation.' };
  const beat = parseApiDate(node.last_heartbeat);
  if (node.health === 'OFFLINE' || node.status === 'OFFLINE' || !beat || Date.now() - beat.getTime() > heartbeatTimeoutSeconds * 1000) {
    return {
      label: 'Offline',
      tone: 'red',
      detail: 'The worker is not sending heartbeats, so its work is moved to other nodes. Check that it is running (agentmesh-worker doctor).',
    };
  }
  if (!node.accepting_workloads) return { label: 'Paused', tone: 'amber', detail: 'Paused in AgentMesh. Running deployments continue; no new ones are placed.' };
  if (!node.worker_available) {
    const why = node.worker_unavailable_reason ?? '';
    return { label: 'Draining', tone: 'amber', detail: `Not taking new work: ${WORKER_REASON[why] ?? why ?? 'reported by the worker'}.` };
  }
  if (node.health === 'DEGRADED') {
    const until = parseApiDate(node.degraded_until);
    if (until && until.getTime() > Date.now()) {
      return {
        label: 'Degraded',
        tone: 'amber',
        detail: `Several placements failed in a row, so it gets no new work until ${until.toLocaleTimeString()}. Check the worker log.`,
      };
    }
    if ((node.recovery_heartbeats ?? 0) < 2) {
      return { label: 'Recovering', tone: 'amber', detail: 'Back after an outage. It gets new work again after a few healthy heartbeats.' };
    }
    return { label: 'Degraded', tone: 'amber', detail: 'Heartbeats are arriving late, so no new work is placed until they are on time again.' };
  }
  if (node.health === 'BUSY') return { label: 'Busy', tone: 'green', detail: 'Running work, and accepting more while it has free capacity.' };
  return { label: 'Accepting work', tone: 'green', detail: 'New deployments can be placed here when they fit.' };
}

export function capacityRows(node: Node) {
  return [
    { label: 'CPU cores', reserved: node.reserved_cpu_cores, allocated: node.allocated_cpu_cores, unit: '' },
    { label: 'Memory', reserved: node.reserved_ram_mb, allocated: node.allocated_ram_mb, unit: 'mb' },
    { label: 'Disk', reserved: node.reserved_disk_mb, allocated: node.allocated_disk_mb, unit: 'mb' },
    { label: 'GPU memory', reserved: node.reserved_vram_mb, allocated: node.allocated_vram_mb, unit: 'mb' },
  ].filter((r) => r.allocated > 0 || r.reserved > 0);
}
