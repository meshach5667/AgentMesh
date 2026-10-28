import { useQuery } from '@tanstack/react-query';
import { WORKER_VERSION } from '../lib/config';

export type WorkerReleaseState = 'published' | 'unpublished' | 'unknown';

/** Asks the dashboard's own server (which asks GitHub) whether the worker release this dashboard points at is published. */
export const useWorkerRelease = (version = WORKER_VERSION) =>
  useQuery({
    queryKey: ['worker-release', version],
    queryFn: async (): Promise<WorkerReleaseState> => {
      try {
        const res = await fetch('/api/worker-release');
        if (!res.ok) return 'unknown';
        const body = (await res.json()) as { state?: WorkerReleaseState };
        return body.state ?? 'unknown';
      } catch {
        return 'unknown';
      }
    },
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
