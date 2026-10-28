import { useQuery } from '@tanstack/react-query';

export type WorkerReleaseState = 'published' | 'unpublished' | 'unknown';

export interface WorkerReleaseInfo {
  state: WorkerReleaseState;
  /** Exact GitHub tag and wheel version, when published. */
  tag?: string;
  version?: string;
}

/** Asks the dashboard's own server (which asks GitHub) for the newest published worker release and its exact tag. */
export const useWorkerRelease = () =>
  useQuery({
    queryKey: ['worker-release'],
    queryFn: async (): Promise<WorkerReleaseInfo> => {
      try {
        const res = await fetch('/api/worker-release');
        if (!res.ok) return { state: 'unknown' };
        return (await res.json()) as WorkerReleaseInfo;
      } catch {
        return { state: 'unknown' };
      }
    },
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
