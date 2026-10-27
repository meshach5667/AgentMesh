import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import {
  IN_PROGRESS_STATUSES,
  type Deployment,
  type DeploymentPricing,
  type Quote,
  type DeploymentConfig,
  type DeploymentEvent,
  type Runtime,
  type UsageRecord,
} from '../types';

const inProgress = (d?: Deployment) => !!d && IN_PROGRESS_STATUSES.includes(d.status);

export const useDeployments = () =>
  useQuery({
    queryKey: ['deployments'],
    queryFn: async () => (await api.get<Deployment[]>('/deployments')).data,
    refetchInterval: (q) => (q.state.data?.some(inProgress) ? 3000 : 15000),
  });

export const useDeployment = (id: string) =>
  useQuery({
    queryKey: ['deployments', id],
    queryFn: async () => (await api.get<Deployment>(`/deployments/${id}`)).data,
    enabled: !!id,
    // Poll quickly while the deployment is moving between states, slowly otherwise (health can change).
    refetchInterval: (q) => (inProgress(q.state.data) ? 2000 : 10000),
  });

export const useDeploymentEvents = (id: string, live: boolean) =>
  useQuery({
    queryKey: ['deployments', id, 'events'],
    queryFn: async () => (await api.get<DeploymentEvent[]>(`/deployments/${id}/events`)).data,
    enabled: !!id,
    refetchInterval: live ? 2000 : 10000,
  });

export const useDeploymentUsage = (id: string) =>
  useQuery({
    queryKey: ['usage', 'deployment', id],
    queryFn: async () => (await api.get<UsageRecord[]>(`/usage/${id}`, { params: { limit: 50 } })).data,
    enabled: !!id,
    refetchInterval: 15000,
  });

export interface CreateDeploymentInput {
  model_id: string;
  runtime?: Runtime;
  config: DeploymentConfig;
  idempotency_key: string;
  max_hourly_price?: string;
  max_token_price?: string;
}

export const useCreateDeployment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateDeploymentInput) => (await api.post<Deployment>('/deployments', payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['deployments'] }),
  });
};

function useDeploymentAction(action: 'stop' | 'restart' | 'delete') {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      action === 'delete'
        ? (await api.delete(`/deployments/${id}`)).data
        : (await api.post(`/deployments/${id}/${action}`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deployments'] });
      qc.invalidateQueries({ queryKey: ['admin', 'deployments'] });
      qc.invalidateQueries({ queryKey: ['api-keys'] });
    },
  });
}

export const useStopDeployment = () => useDeploymentAction('stop');
export const useRestartDeployment = () => useDeploymentAction('restart');
export const useDeleteDeployment = () => useDeploymentAction('delete');

/** Price a deployment before creating it (reserves nothing). */
export const useQuote = (input: Omit<CreateDeploymentInput, 'idempotency_key'>, enabled = true) =>
  useQuery({
    queryKey: ['deployments', 'quote', input],
    queryFn: async () => (await api.post<Quote>('/deployments/quote', input)).data,
    enabled,
    staleTime: 15000,
    retry: false,
  });

/** The rates a deployment is billed at now on its machine. */
export const useDeploymentPricing = (id: string) =>
  useQuery({
    queryKey: ['deployments', id, 'pricing'],
    queryFn: async () => (await api.get<DeploymentPricing>(`/deployments/${id}/pricing`)).data,
    enabled: !!id,
    refetchInterval: 60000,
  });
