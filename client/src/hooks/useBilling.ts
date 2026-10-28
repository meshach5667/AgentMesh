import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { CostEstimate, CostSummary, EstimateScope, Market } from '../types';

/** Price ranges per currency across machines that can take work (providers set their own prices). */
export const useMarket = () =>
  useQuery({ queryKey: ['billing', 'market'], queryFn: async () => (await api.get<Market>('/billing/market')).data });

/** Estimated cost of each window of use (estimates, not payments: customers pay providers directly). */
export const useEstimates = (deploymentId?: string, scope?: EstimateScope) =>
  useQuery({
    queryKey: ['billing', 'estimates', deploymentId ?? 'all', scope ?? 'default'],
    queryFn: async () =>
      (await api.get<CostEstimate[]>('/billing/estimates', { params: { deployment_id: deploymentId, scope, limit: 500 } })).data,
    refetchInterval: 60000,
  });

export const useEstimateSummary = (days = 30, scope?: EstimateScope) =>
  useQuery({
    queryKey: ['billing', 'estimates-summary', days, scope ?? 'default'],
    queryFn: async () => (await api.get<CostSummary>('/billing/estimates/summary', { params: { days, scope } })).data,
    refetchInterval: 60000,
  });
