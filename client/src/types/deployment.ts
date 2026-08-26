import { Model } from './model';
import { Node } from './node';

export type DeploymentStatus = 'REQUESTED' | 'VALIDATING' | 'SCHEDULING' | 'ASSIGNED' | 'DEPLOYING' | 'HEALTH_CHECK' | 'RUNNING' | 'STOPPING' | 'STOPPED' | 'FAILED';

export interface Deployment {
  id: string;
  customer_id: string;
  model_id: string;
  node_id: string;
  status: DeploymentStatus;
  endpoint: string | null;
  config: Record<string, any>;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  model?: Model;
  node?: Node;
  total_cost?: number;
}
