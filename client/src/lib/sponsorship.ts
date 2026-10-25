import { CONTROL_PLANE_URL } from './config';
import type { SponsorCategory } from '@/types';

export const CATEGORY_LABEL: Record<SponsorCategory, string> = {
  ai_tools: 'AI tools',
  gpu_hardware: 'GPU hardware',
  infrastructure: 'Infrastructure',
};

/** Absolute URL of a sponsored item's click endpoint (it counts the click and redirects to the sponsor). Only API
 * paths are accepted, so a malformed item can never send viewers elsewhere. */
export function clickUrl(path: string, base = CONTROL_PLANE_URL): string | null {
  return /^\/api\/v\d+\/sponsored\/[0-9a-f-]{36}\/click\?/.test(path) ? `${base.replace(/\/$/, '')}${path}` : null;
}

const DISMISSED = 'agentmesh.sponsored.dismissed';

/** Campaigns this viewer closed, kept in their own browser only. */
export function dismissedIds(storage: Pick<Storage, 'getItem'> | undefined = globalThis.localStorage): string[] {
  try {
    const raw = storage?.getItem(DISMISSED);
    const ids = raw ? JSON.parse(raw) : [];
    return Array.isArray(ids) ? ids.filter((i) => typeof i === 'string') : [];
  } catch {
    return [];
  }
}

export function dismiss(id: string, storage: Pick<Storage, 'getItem' | 'setItem'> | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(DISMISSED, JSON.stringify([...dismissedIds(storage), id].slice(-50)));
  } catch {
    // Private windows may refuse storage; the item then simply returns on the next visit.
  }
}

/** Earned revenue of a campaign, formatted rate description. */
export function pricingLabel(model: 'cpm' | 'cpc' | 'flat'): string {
  return { cpm: 'per 1,000 impressions', cpc: 'per click', flat: 'flat fee' }[model];
}
