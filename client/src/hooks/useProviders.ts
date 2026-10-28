import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import type { PaymentProfile, ProviderCard, ProviderDetail, ProviderOffer } from '../types';

/** Providers with machines that can take work now (aggregates only; no machine is named). */
export const useOffers = () =>
  useQuery({ queryKey: ['providers'], queryFn: async () => (await api.get<ProviderOffer[]>('/providers')).data, refetchInterval: 30000 });

export const useProvider = (id: string | null | undefined) =>
  useQuery({
    queryKey: ['providers', id],
    queryFn: async () => (await api.get<ProviderDetail>(`/providers/${id}`)).data,
    enabled: !!id,
  });

export const useMyProviderProfile = () =>
  useQuery({ queryKey: ['providers', 'me'], queryFn: async () => (await api.get<ProviderCard>('/providers/me')).data });

export interface ProfileInput {
  display_name: string;
  description: string | null;
  payment: PaymentProfile;
}

export const useUpdateProviderProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProfileInput) => (await api.put<ProviderCard>('/providers/me', body)).data,
    onSuccess: (data) => {
      qc.setQueryData(['providers', 'me'], data);
      qc.invalidateQueries({ queryKey: ['providers'] });
    },
  });
};
