import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import { Deployment } from '../types';

export const useDeployments = () => {
  return useQuery({
    queryKey: ['deployments'],
    queryFn: async () => {
      const { data } = await api.get<Deployment[]>('/deployments');
      return data;
    },
  });
};

export const useDeployment = (id: string) => {
  return useQuery({
    queryKey: ['deployments', id],
    queryFn: async () => {
      const { data } = await api.get<Deployment>(`/deployments/${id}`);
      return data;
    },
    enabled: !!id,
  });
};

export const useCreateDeployment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { model_id: string; config?: Record<string, unknown> }) => {
      const { data } = await api.post<Deployment>('/deployments', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] });
    },
  });
};

export const useStopDeployment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/deployments/${id}/stop`);
      return data;
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] });
      queryClient.invalidateQueries({ queryKey: ['deployments', id] });
    },
  });
};
