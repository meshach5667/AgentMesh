import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';

export interface Workload {
  id: string;
  model_id: string;
  node_id: string | null;
  status: string;
  result: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export function useSubmitInference() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { model: string; input: Record<string, unknown>; requirements?: Record<string, unknown> }) => {
      const { data } = await api.post<Workload>('/inference', payload);
      return data;
    },
    onSuccess: (workload) => {
      queryClient.setQueryData(['workloads', workload.id], workload);
    },
  });
}

export function useWorkload(id: string | null) {
  return useQuery({
    queryKey: ['workloads', id],
    queryFn: async () => (await api.get<Workload>(`/workloads/${id}`)).data,
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ['COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED'].includes(status) ? false : 2000;
    },
  });
}