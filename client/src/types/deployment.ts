import { Model } from './model';
import { Node } from './node';

// Mirrors the control plane lifecycle (server/app/services/deployment_lifecycle.py).
export type DeploymentStatus =
  | 'REQUESTED'
  | 'SCHEDULED'
  | 'PROVISIONING'
  | 'STARTING'
  | 'READY'
  | 'UNHEALTHY'
  | 'STOPPING'
  | 'STOPPED'
  | 'FAILED'
  | 'CANCELLED';

export interface Deployment {
  id: string;
  customer_id: string;
  model_id: string;
  node_id: string;
  status: DeploymentStatus;
  endpoint: string | null;
  runtime?: string | null;
  model_tag?: string | null;
  model_digest?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  ready_at?: string | null;
  cleanup_status?: string | null;
  config: Record<string, unknown>;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  model?: Partial<Model>;
  node?: Partial<Node>;
  total_cost?: number;
}
