import { REPO_SLUG, WORKER_VERSION } from '@/lib/config';
import { workerTag } from '@/lib/worker';
import type { WorkerReleaseState } from '@/hooks/useWorkerRelease';

const TTL_MS = 5 * 60 * 1000;
let cached: { state: WorkerReleaseState; at: number } | null = null;

/** Whether this dashboard's worker release is on GitHub. Asked server-side so the page's CSP never has to allow
 * api.github.com, and cached so visitors share GitHub's unauthenticated rate limit. Unknown results are not cached. */
export async function GET() {
  if (cached && Date.now() - cached.at < TTL_MS) return Response.json({ state: cached.state });
  let state: WorkerReleaseState = 'unknown';
  try {
    const res = await fetch(`https://api.github.com/repos/${REPO_SLUG}/releases/tags/${workerTag(WORKER_VERSION)}`, {
      headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'agentmesh-dashboard' },
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) state = 'published';
    else if (res.status === 404) state = 'unpublished';
  } catch {
    // GitHub unreachable: report unknown rather than claiming the release is missing.
  }
  if (state !== 'unknown') cached = { state, at: Date.now() };
  return Response.json({ state });
}
