// Mirrors server/app/schemas/model.py.
export type Runtime = 'ollama' | 'llamacpp' | 'vllm';

/** How one runtime serves a model, from a pinned source. */
export interface ModelArtifact {
  id: string;
  runtime: Runtime;
  source_type: 'ollama' | 'huggingface';
  reference: string;
  revision: string | null;
  file: string | null;
  sha256: string | null;
  size_bytes: number | null;
  format: string | null;
  quantization: string | null;
  min_ram_mb: number;
  min_disk_mb: number;
  min_vram_mb: number;
  min_cpu_cores: number;
  gpu_required: boolean;
  requirements_estimated: boolean;
  is_enabled: boolean;
  /** Last time a deployment of this artifact passed its readiness test. */
  last_ready_at: string | null;
}

export interface Model {
  id: string;
  name: string;
  version: string | null;
  runtime: string | null;
  is_approved: boolean;
  model_tag: string | null;
  publisher: string | null;
  family: string | null;
  parameter_size: string | null;
  quantization: string | null;
  format: string | null;
  license: string | null;
  context_length: number | null;
  download_size_mb: number | null;
  min_ram_mb: number | null;
  min_disk_mb: number | null;
  min_vram_mb: number | null;
  min_cpu_cores: number | null;
  gpu_required: boolean;
  requirements_estimated: boolean;
  artifacts: ModelArtifact[];
}
