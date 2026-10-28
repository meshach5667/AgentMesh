import { REPO_SLUG } from '@/lib/config';
import type { WorkerReleaseInfo } from '@/hooks/useWorkerRelease';
import { pickWorkerRelease, type GitHubRelease } from '@/lib/workerRelease';

const TTL_MS = 5 * 60 * 1000;
let cached: { info: WorkerReleaseInfo; at: number } | null = null;

/** Asked server-side so the page's CSP never has to allow api.github.com, and cached so visitors share GitHub's
 * unauthenticated rate limit. Unknown results are not cached. */
export async function GET() {
  if (cached && Date.now() - cached.at < TTL_MS) return Response.json(cached.info);
  let info: WorkerReleaseInfo = { state: 'unknown' };
  try {
    const res = await fetch(`https://api.github.com/repos/${REPO_SLUG}/releases?per_page=30`, {
      headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'agentmesh-dashboard' },
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) info = pickWorkerRelease((await res.json()) as GitHubRelease[]);
  } catch {
    // GitHub unreachable: report unknown rather than claiming no release exists.
  }
  if (info.state !== 'unknown') cached = { info, at: Date.now() };
  return Response.json(info);
}
