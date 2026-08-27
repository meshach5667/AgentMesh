export type NodeStatus =
  | 'REGISTERING'
  | 'ONLINE'
  | 'AVAILABLE'
  | 'BUSY'
  | 'DEGRADED'
  | 'OFFLINE'
  | 'SUSPENDED';

export interface NodeHardware {
  cpu_model: string;
  cpu_cores: number;
  ram_gb: number;
  storage_gb: number;
  gpu_model?: string | null;
  gpu_count: number;
  gpu_vram_gb?: number | null;
  os_info: string;
  capabilities?: string[];
}

export interface NodePricing {
  gpu_hour_price: number;
  cpu_hour_price: number;
  ram_gb_hour_price: number;
  storage_gb_month_price: number;
  bandwidth_gb_price: number;
  pricing_mode: 'PROVIDER_FIXED' | 'AGENTMESH_RECOMMENDED';
  currency: string;
}

export interface Node {
  id: string;
  owner_id: string;
  name: string;
  status: NodeStatus;
  region: string;
  last_heartbeat: string;
  reputation_score: number;
  created_at: string;
  hardware?: NodeHardware;
  pricing?: NodePricing;
}
export interface NodeMetrics {
  gpu_utilization_percent: number;
}

export interface ExtendedNode extends Node {
  metrics?: NodeMetrics;
}
