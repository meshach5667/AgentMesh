export interface Model {
  id: string;
  name: string;
  version: string;
  runtime: string;
  source: string;
  minimum_vram: number;
  minimum_ram: number;
  minimum_cpu: number;
  storage_requirement: number;
  is_approved: boolean;
}

export interface ExtendedModel extends Model {
  supported_gpu_families?: string[];
}
