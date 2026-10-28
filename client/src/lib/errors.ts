import { isAxiosError } from 'axios';

/** Placement failure returned with HTTP 503 by POST /deployments. */
export interface NoCapacityDetail {
  code: string;
  message?: string;
  reasons?: Record<string, number>;
  by_runtime?: Record<string, { message?: string; reasons?: Record<string, number> }>;
  requirements?: Record<string, unknown>;
}

// Reason codes from server/app/services/scheduler_service.py.
const REASON_TEXT: Record<string, string> = {
  provider_unavailable: 'node offline, paused, or outside its availability schedule',
  unsupported_runtime: 'runtime not installed on the node',
  incompatible_hardware: 'hardware does not match (for example, a GPU is required)',
  insufficient_capacity: 'not enough free CPU, memory, disk or GPU memory',
  region_mismatch: 'not in the requested region',
  previously_failed: 'this deployment already failed on the node',
  community_not_accepted: 'the provider has not opted in to community models',
  over_price_limit: 'charges more than your price limit',
};

export function reasonText(reason: string): string {
  return REASON_TEXT[reason] ?? reason.replace(/_/g, ' ');
}

export function noCapacityDetail(err: unknown): NoCapacityDetail | null {
  if (!isAxiosError(err) || err.response?.status !== 503) return null;
  const detail = err.response.data?.detail;
  return detail && typeof detail === 'object' && 'code' in detail ? (detail as NoCapacityDetail) : null;
}

/** Human-readable message for an API error (FastAPI `detail` as string, validation list, or object). */
export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (isAxiosError(err)) {
    if (!err.response) return 'Cannot reach the AgentMesh API. Check that the server is running.';
    const detail = err.response.data?.detail ?? err.response.data?.error;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { loc?: unknown[]; msg?: string }) => {
          const field = (d.loc ?? []).filter((p) => p !== 'body').join('.');
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join('; ');
    }
    if (detail && typeof detail === 'object') {
      const d = detail as NoCapacityDetail;
      if (d.reasons && Object.keys(d.reasons).length) {
        const why = Object.entries(d.reasons)
          .map(([r, n]) => `${reasonText(r)} (${n})`)
          .join(', ');
        return `${d.message ?? 'No node can run this deployment right now'}: ${why}`;
      }
      return d.message ?? d.code ?? fallback;
    }
    return `Request failed (HTTP ${err.response.status})`;
  }
  return err instanceof Error ? err.message : fallback;
}

/**
 * Field-level messages from a 422 response, keyed by the last named field of each error location (list items become
 * "<list>-<index>", e.g. a bad payment link URL at payment.links[0].url becomes "link-0"). Empty for other errors.
 */
export function fieldErrors(err: unknown): Record<string, string> {
  if (!isAxiosError(err) || err.response?.status !== 422) return {};
  const detail = err.response.data?.detail;
  if (!Array.isArray(detail)) return {};
  const out: Record<string, string> = {};
  for (const d of detail as { loc?: (string | number)[]; msg?: string }[]) {
    const loc = (d.loc ?? []).filter((p) => p !== 'body');
    const idx = loc.findIndex((p) => typeof p === 'number');
    let key: string | undefined;
    if (idx > 0) key = `${String(loc[idx - 1]).replace(/s$/, '')}-${loc[idx]}`;
    else key = [...loc].reverse().find((p) => typeof p === 'string') as string | undefined;
    if (key && d.msg) out[key] = d.msg.replace(/^Value error, /, '');
  }
  return out;
}
