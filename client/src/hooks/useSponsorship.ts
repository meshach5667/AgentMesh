import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import type { AdSettings, Campaign, CampaignInput, CampaignStatus, Placement, SponsoredSlot } from '../types';

/** What a slot shows. Empty (and nothing rendered) while advertising or the slot is off. */
export const useSponsored = (placement: Placement) =>
  useQuery({
    queryKey: ['sponsored', placement],
    queryFn: async () => (await api.get<SponsoredSlot>('/sponsored', { params: { placement } })).data,
    staleTime: 5 * 60_000,
    retry: false,
  });

export async function reportImpression(id: string, placement: Placement, token: string): Promise<void> {
  try {
    await api.post(`/sponsored/${id}/impression`, { placement, token });
  } catch {
    // Measurement must never disturb the page.
  }
}

// --- operator ---

export const useAdSettings = () =>
  useQuery({ queryKey: ['admin', 'ads', 'settings'], queryFn: async () => (await api.get<AdSettings>('/admin/ads/settings')).data });

export const useCampaigns = () =>
  useQuery({
    queryKey: ['admin', 'ads', 'campaigns'],
    queryFn: async () => (await api.get<Campaign[]>('/admin/ads/campaigns')).data,
    refetchInterval: 30000,
  });

function useInvalidateAds() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['admin', 'ads'] });
    qc.invalidateQueries({ queryKey: ['sponsored'] });
  };
}

export const useUpdateAdSettings = () => {
  const invalidate = useInvalidateAds();
  return useMutation({
    mutationFn: async (body: { enabled?: boolean; placements?: Record<string, { enabled: boolean; max_items: number }> }) =>
      (await api.put<AdSettings>('/admin/ads/settings', body)).data,
    onSuccess: invalidate,
  });
};

export const useSaveCampaign = () => {
  const invalidate = useInvalidateAds();
  return useMutation({
    mutationFn: async ({ id, body }: { id?: string; body: CampaignInput }) =>
      id ? (await api.put<Campaign>(`/admin/ads/campaigns/${id}`, body)).data : (await api.post<Campaign>('/admin/ads/campaigns', body)).data,
    onSuccess: invalidate,
  });
};

export const useSetCampaignStatus = () => {
  const invalidate = useInvalidateAds();
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: CampaignStatus }) =>
      (await api.post<Campaign>(`/admin/ads/campaigns/${id}/status`, { status })).data,
    onSuccess: invalidate,
  });
};
