import type { Runtime } from './model';

// Mirrors the control plane lifecycle (server/app/services/deployment_lifecycle.py).
export type DeploymentStatus =
  | 'REQUESTED'
  | 'PENDING'
  | 'NEEDS_ATTENTION'
  | 'SCHEDULED'
  | 'PROVISIONING'
  | 'STARTING'
  | 'READY'
  | 'UNHEALTHY'
  | 'STOPPING'
  | 'STOPPED'
  | 'FAILED'
  | 'CANCELLED';

export const TERMINAL_STATUSES: DeploymentStatus[] = ['STOPPED', 'FAILED', 'CANCELLED'];
export const IN_PROGRESS_STATUSES: DeploymentStatus[] = ['REQUESTED', 'SCHEDULED', 'PROVISIONING', 'STARTING', 'STOPPING'];
/** Waiting for a node: PENDING retries automatically; NEEDS_ATTENTION waits for the customer. */
export const WAITING_STATUSES: DeploymentStatus[] = ['PENDING', 'NEEDS_ATTENTION'];

export type FailoverPolicy = 'any_provider' | 'same_provider' | 'manual';

export interface DeploymentConfig {
  num_ctx?: number;
  region?: string | null;
  require_gpu?: boolean;
}

export interface Deployment {
  id: string;
  customer_id: string;
  model_id: string;
  node_id: string | null;
  status: DeploymentStatus;
  /** Runtime-native base URL (Ollama API for Ollama deployments, otherwise OpenAI-compatible). */
  endpoint: string | null;
  /** OpenAI-compatible base URL; works for every runtime. */
  openai_base_url: string | null;
  runtime: Runtime | null;
  artifact_id: string | null;
  model_tag: string | null;
  model_digest: string | null;
  config: DeploymentConfig | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  ready_at: string | null;
  ended_at: string | null;
  cleanup_status: string | null;
  schedule_attempts: number;
  restart_count: number;
  /** Price limits for every placement, in ``currency``; null means no explicit limit. */
  currency: string | null;
  max_hourly_price: string | null;
  max_token_price: string | null;
  /** Placement is restricted to this provider's machines when set. */
  provider_id: string | null;
  failover_policy: FailoverPolicy;
  attempt_id: string | null;
  next_placement_at: string | null;
  pending_since: string | null;
  placement_retries: number;
}

export interface DeploymentAttempt {
  id: string;
  number: number;
  active: boolean;
  state: 'assigned' | 'running' | 'ended';
  outcome: 'node_failed' | 'workload_failed' | 'stopped' | 'superseded' | null;
  error_code: string | null;
  error_message: string | null;
  assigned_at: string;
  ready_at: string | null;
  ended_at: string | null;
  rates: Record<string, string> | null;
  provider: string | null;
}

export interface DeploymentEvent {
  from_status: string | null;
  to_status: string | null;
  actor: string;
  message: string | null;
  kind: string | null;
  attempt: number | null;
  created_at: string;
}
