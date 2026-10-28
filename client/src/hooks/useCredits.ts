import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import type { ConnectedGateway, CreditPayment, Credits, GatewayName } from '../types';

/** Customers: credit with each provider and payments. Providers: customers' credit with them and payments to them. */
export const useCredits = () =>
  useQuery({ queryKey: ['credits'], queryFn: async () => (await api.get<Credits>('/credits')).data, refetchInterval: 15000 });

export interface TopupInput {
  provider_id: string;
  amount: string;
  currency: string;
  method: 'gateway' | 'manual';
  gateway?: GatewayName;
  reference?: string;
  note?: string;
}

export const useStartTopup = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: TopupInput) => (await api.post<CreditPayment>('/credits/topups', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credits'] }),
  });
};

export const useVerifyTopup = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.post<CreditPayment>(`/credits/topups/${id}/verify`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['credits'] });
      qc.invalidateQueries({ queryKey: ['deployments'] });
    },
  });
};

/** Providers: confirm or reject a manual payment made to them. */
export const useDecideTopup = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, accept, reason }: { id: string; accept: boolean; reason?: string }) =>
      (await api.post<CreditPayment>(`/credits/topups/${id}/decision`, { accept, reason: reason || null })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['credits'] }),
  });
};

export const useGateways = () =>
  useQuery({ queryKey: ['gateways'], queryFn: async () => (await api.get<ConnectedGateway[]>('/providers/me/gateways')).data });

export const useConnectGateway = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ gateway, secret_key }: { gateway: GatewayName; secret_key: string }) =>
      (await api.put<ConnectedGateway>(`/providers/me/gateways/${gateway}`, { secret_key })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gateways'] }),
  });
};

export const useDisconnectGateway = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (gateway: GatewayName) => api.delete(`/providers/me/gateways/${gateway}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gateways'] }),
  });
};
