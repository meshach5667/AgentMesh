// Mirrors server/app/schemas/node.py (NodeOut).
export type NodeStatus =
  | 'REGISTERING'
  | 'ONLINE'
  | 'AVAILABLE'
  | 'BUSY'
  | 'DEGRADED'
  | 'OFFLINE'
  | 'SUSPENDED'
  | 'QUARANTINED'
  | 'REVOKED';

/** Derived by the control plane from health evidence; drives whether the node gets new work. */
export type NodeHealth =
  | 'ACTIVE'
  | 'BUSY'
  | 'DEGRADED'
  | 'DRAINING'
  | 'OFFLINE'
  | 'SUSPENDED'
  | 'QUARANTINED'
  | 'REVOKED'
  | 'REGISTERING';

export interface NodeRuntime {
  name: string;
  version?: string;
  backend?: string;
  available?: boolean;
  gpu?: boolean;
  limits_enforced?: boolean;
  detail?: string;
}

export interface Node {
  id: string;
  owner_id: string;
  name: string | null;
  status: NodeStatus;
  region: string | null;
  reputation_score: number | null;
  last_heartbeat: string | null;
  created_at: string;
  mode: 'docker' | 'agent' | string | null;
  worker_version: string | null;
  protocol_version: number | null;
  runtimes: NodeRuntime[] | null;
  /** Set by the provider or operator in AgentMesh ("pause"). */
  accepting_workloads: boolean;
  /** Provider opt-in to unreviewed models customers imported from Hugging Face. Off by default. */
  accepts_community_models: boolean;
  /** Reported by the worker itself (local pause, drain, or availability schedule). */
  worker_available: boolean;
  worker_unavailable_reason: string | null;
  allocated_cpu_cores: number;
  allocated_ram_mb: number;
  allocated_disk_mb: number;
  allocated_vram_mb: number;
  reserved_cpu_cores: number;
  reserved_ram_mb: number;
  reserved_disk_mb: number;
  reserved_vram_mb: number;
  last_metrics: Record<string, number> | null;
  /** Failure cooldown after repeated failed placements, if any. */
  degraded_until: string | null;
  consecutive_failures: number;
  recovery_heartbeats: number;
  health: NodeHealth | null;
  /** Whether the scheduler may place new work here right now. */
  schedulable: boolean;
}

export interface NodeEvent {
  action: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface EnrollmentToken {
  token: string;
  expires_at: string;
}
