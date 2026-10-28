'use client';

import { CodeBlock } from '@/components/common/CodeBlock';
import { Notice } from '@/components/common/Notices';
import { useWorkerRelease, type WorkerReleaseInfo } from '@/hooks/useWorkerRelease';
import { RELEASES_URL, WORKER_VERSION } from '@/lib/config';
import { agentInstallCommand, uninstallCommand, workerReleaseUrl, workerTag, type WorkerRelease } from '@/lib/worker';

/** The release to show commands for: the one GitHub reports, or this dashboard's own version until it answers. */
export function releaseOrDefault(info: WorkerReleaseInfo | undefined): WorkerRelease {
  return info?.state === 'published' && info.tag && info.version
    ? { tag: info.tag, version: info.version }
    : { tag: workerTag(), version: WORKER_VERSION };
}

export function ReleaseStatus() {
  const { data, isPending } = useWorkerRelease();
  if (isPending) return <Notice title="Checking GitHub for the latest worker release…">Looking it up on GitHub.</Notice>;
  if (data?.state === 'published') {
    return (
      <Notice title={`Worker ${data.version} is published`}>
        Release tag <code className="font-mono">{data.tag}</code> on the{' '}
        <a href={workerReleaseUrl(data.tag)} className="underline underline-offset-4" target="_blank" rel="noreferrer">
          release page
        </a>
        ; the commands below use it.
      </Notice>
    );
  }
  return (
    <Notice tone="warning" title={data?.state === 'unpublished' ? 'No worker release has been published yet' : 'Could not check the release'}>
      {data?.state === 'unpublished' ? 'The download commands below will work once a release with the worker files appears on ' : 'Check '}
      <a href={RELEASES_URL} className="underline underline-offset-4" target="_blank" rel="noreferrer">
        GitHub Releases
      </a>
      {data?.state === 'unpublished' ? '. Until then, install from source.' : ' before using the download commands.'}
    </Notice>
  );
}

/** Install or uninstall command for the exact published release tag. */
export function ReleaseCommand({ kind, title }: { kind: 'install' | 'uninstall'; title?: string }) {
  const { tag, version } = releaseOrDefault(useWorkerRelease().data);
  return (
    <div>
      {title && <p className="mb-1.5 font-mono text-xs text-muted-foreground">{title}</p>}
      <CodeBlock code={kind === 'install' ? agentInstallCommand({ tag, version }) : uninstallCommand(version)} />
    </div>
  );
}
