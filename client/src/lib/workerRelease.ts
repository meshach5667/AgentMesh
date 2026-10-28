import type { WorkerReleaseInfo } from '@/hooks/useWorkerRelease';

const WHEEL = /^agentmesh_worker-(\d+\.\d+\.\d+(?:[a-z0-9.]*)?)-py3-none-any\.whl$/;
// The tag ends up in a shell command providers paste, so only plain tag characters are accepted.
const SAFE_TAG = /^[A-Za-z0-9._-]{1,100}$/;
const REQUIRED = ['install.sh', 'uninstall.sh', 'SHA256SUMS'];

export interface GitHubRelease {
  tag_name: string;
  draft: boolean;
  prerelease: boolean;
  assets: { name: string }[];
}

/** The newest published GitHub release that carries the worker assets, with its exact tag and wheel version.
 * Releases without the wheel, install.sh, uninstall.sh and SHA256SUMS (such as app releases) are skipped. */
export function pickWorkerRelease(releases: GitHubRelease[]): WorkerReleaseInfo {
  for (const r of releases) {
    if (r.draft || r.prerelease || !SAFE_TAG.test(r.tag_name)) continue;
    const names = r.assets.map((a) => a.name);
    const version = names.map((n) => WHEEL.exec(n)?.[1]).find(Boolean);
    if (version && REQUIRED.every((n) => names.includes(n))) return { state: 'published', tag: r.tag_name, version };
  }
  return { state: 'unpublished' };
}
