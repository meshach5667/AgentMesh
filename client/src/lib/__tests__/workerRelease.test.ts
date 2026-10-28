import { agentInstallCommand } from '../worker';
import { pickWorkerRelease, type GitHubRelease } from '../workerRelease';

const assets = (...names: string[]) => names.map((name) => ({ name }));
const WORKER_FILES = ['install.sh', 'uninstall.sh', 'SHA256SUMS'];
const rel = (tag_name: string, names: string[], extra: Partial<GitHubRelease> = {}): GitHubRelease => ({
  tag_name,
  draft: false,
  prerelease: false,
  assets: assets(...names),
  ...extra,
});

describe('picking the worker release from GitHub', () => {
  it('skips releases without the worker files and returns the exact tag', () => {
    // Shaped like the repository's real list: app releases without assets around a worker release.
    const releases = [rel('0.3.1', []), rel('worker-v0.3.0', ['agentmesh_worker-0.3.0-py3-none-any.whl', ...WORKER_FILES]), rel('0.0.3', [])];
    expect(pickWorkerRelease(releases)).toEqual({ state: 'published', tag: 'worker-v0.3.0', version: '0.3.0' });
  });

  it('takes the newest complete release, whatever its tag is called', () => {
    const releases = [
      rel('v0.4.0', ['agentmesh_worker-0.4.0-py3-none-any.whl', ...WORKER_FILES]),
      rel('worker-v0.3.0', ['agentmesh_worker-0.3.0-py3-none-any.whl', ...WORKER_FILES]),
    ];
    expect(pickWorkerRelease(releases)).toMatchObject({ tag: 'v0.4.0', version: '0.4.0' });
  });

  it('ignores drafts, prereleases, incomplete releases and unsafe tags', () => {
    const wheel = 'agentmesh_worker-0.5.0-py3-none-any.whl';
    expect(
      pickWorkerRelease([
        rel('w1', [wheel, ...WORKER_FILES], { draft: true }),
        rel('w2', [wheel, ...WORKER_FILES], { prerelease: true }),
        rel('w3', [wheel, 'install.sh']),
        rel('w4;rm -rf ~', [wheel, ...WORKER_FILES]),
      ]),
    ).toEqual({ state: 'unpublished' });
  });

  it('builds download URLs from the exact tag and the wheel version', () => {
    const cmd = agentInstallCommand({ tag: 'v0.4.0', version: '0.4.0' });
    expect(cmd).toContain('BASE=https://github.com/meshach5667/AgentMesh/releases/download/v0.4.0');
    expect(cmd).toContain('VERSION=0.4.0');
  });
});
