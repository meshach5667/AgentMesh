import { cn } from '@/lib/utils';

const TONE: Record<string, string> = {
  green: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  blue: 'bg-brand-soft text-brand border-brand/25',
  amber: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30',
  red: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30',
  gray: 'bg-muted text-muted-foreground border-border',
};

const STATUS_TONE: Record<string, keyof typeof TONE> = {
  // deployments
  READY: 'green',
  REQUESTED: 'blue',
  SCHEDULED: 'blue',
  PROVISIONING: 'blue',
  STARTING: 'blue',
  STOPPING: 'amber',
  UNHEALTHY: 'amber',
  PENDING: 'amber',
  NEEDS_ATTENTION: 'red',
  FAILED: 'red',
  STOPPED: 'gray',
  CANCELLED: 'gray',
  // AI deployment runs
  PLANNING: 'blue',
  SUBMITTING: 'blue',
  DEPLOYING: 'blue',
  VERIFYING: 'blue',
  RECOVERING: 'amber',
  COMPLETED: 'gray',
  // nodes (status and derived health)
  ONLINE: 'green',
  ACTIVE: 'green',
  AVAILABLE: 'green',
  BUSY: 'blue',
  REGISTERING: 'blue',
  DEGRADED: 'amber',
  DRAINING: 'amber',
  OFFLINE: 'red',
  SUSPENDED: 'red',
  QUARANTINED: 'red',
  REVOKED: 'red',
  // sponsorship campaigns
  draft: 'gray',
  active: 'green',
  paused: 'amber',
  ended: 'gray',
};

/** Words, not codes: status is never conveyed by colour alone. */
const STATUS_LABEL: Record<string, string> = {
  REQUESTED: 'Queued',
  SCHEDULED: 'Assigned',
  PROVISIONING: 'Provisioning',
  STARTING: 'Starting',
  READY: 'Running',
  UNHEALTHY: 'Unhealthy',
  PENDING: 'Waiting for a node',
  NEEDS_ATTENTION: 'Needs your action',
  STOPPING: 'Stopping',
  STOPPED: 'Stopped',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
  ONLINE: 'Online',
  ACTIVE: 'Active',
  BUSY: 'Busy',
  DEGRADED: 'Degraded',
  DRAINING: 'Draining',
  OFFLINE: 'Offline',
  SUSPENDED: 'Suspended',
  QUARANTINED: 'Quarantined',
  REVOKED: 'Revoked',
  REGISTERING: 'Registering',
};

export function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status.charAt(0) + status.slice(1).toLowerCase().replace(/_/g, ' ');
}

const PULSE = new Set(['REQUESTED', 'SCHEDULED', 'PROVISIONING', 'STARTING', 'STOPPING', 'PENDING', 'PLANNING', 'SUBMITTING', 'DEPLOYING', 'VERIFYING', 'RECOVERING']);

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const tone = TONE[STATUS_TONE[status] ?? 'gray'];
  return (
    <span
      data-status={status}
      title={status}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-[11px] font-medium tracking-wide whitespace-nowrap',
        tone,
        className,
      )}
    >
      <span aria-hidden className={cn('size-1.5 rounded-full bg-current', PULSE.has(status) && 'motion-safe:animate-pulse')} />
      {statusLabel(status)}
    </span>
  );
}

export function Pill({ children, tone = 'gray', className }: { children: React.ReactNode; tone?: keyof typeof TONE; className?: string }) {
  return (
    <span className={cn('inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-medium', TONE[tone], className)}>
      {children}
    </span>
  );
}
