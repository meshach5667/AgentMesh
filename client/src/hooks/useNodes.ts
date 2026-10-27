import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import type { DefaultPrices, EnrollmentToken, Node, NodePricing, Prices } from '../types';

export const useNodes = () =>
  useQuery({
    queryKey: ['nodes'],
    queryFn: async () => (await api.get<Node[]>('/nodes')).data,
    refetchInterval: 15000,
  });

export const useNode = (id: string) =>
  useQuery({
    queryKey: ['nodes', id],
    queryFn: async () => (await api.get<Node>(`/nodes/${id}`)).data,
    enabled: !!id,
    refetchInterval: 10000,
  });

export const useCreateEnrollmentToken = () =>
  useMutation({
    mutationFn: async (payload: { name?: string; region?: string }) =>
      (await api.post<EnrollmentToken>('/nodes/enrollment-tokens', payload)).data,
  });

function useNodeMutation<T>(fn: (arg: T) => Promise<Node>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (node) => {
      qc.setQueryData(['nodes', node.id], node);
      qc.invalidateQueries({ queryKey: ['nodes'] });
      qc.invalidateQueries({ queryKey: ['admin'] });
    },
  });
}

/** Pause (false) or resume (true) scheduling onto a node. Running deployments are not stopped. */
export const useSetAccepting = () =>
  useNodeMutation(async ({ id, accepting }: { id: string; accepting: boolean }) =>
    (await api.patch<Node>(`/nodes/${id}`, { accepting_workloads: accepting })).data,
  );

/** Opt a node in to (true) or out of (false) unreviewed community models. Only the provider can opt in. */
export const useSetAcceptsCommunity = () =>
  useNodeMutation(async ({ id, accept }: { id: string; accept: boolean }) =>
    (await api.patch<Node>(`/nodes/${id}`, { accepts_community_models: accept })).data,
  );

export const useRevokeNode = () =>
  useNodeMutation(async (id: string) => (await api.post<Node>(`/nodes/${id}/revoke`)).data);

/** What a machine charges, its price history and the network prices for comparison. */
export const useNodePricing = (id: string) =>
  useQuery({
    queryKey: ['nodes', id, 'pricing'],
    queryFn: async () => (await api.get<NodePricing>(`/nodes/${id}/pricing`)).data,
    enabled: !!id,
  });

export const useSetNodePricing = (id: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (prices: Prices) => (await api.put<NodePricing>(`/nodes/${id}/pricing`, prices)).data,
    onSuccess: (data) => qc.setQueryData(['nodes', id, 'pricing'], data),
  });
};

export const useDefaultPrices = () =>
  useQuery({
    queryKey: ['nodes', 'default-prices'],
    queryFn: async () => (await api.get<DefaultPrices>('/nodes/pricing/default')).data,
  });

export const useSetDefaultPrices = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Prices & { apply_to_existing: boolean }) =>
      (await api.put<DefaultPrices>('/nodes/pricing/default', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['nodes'] }),
  });
};
