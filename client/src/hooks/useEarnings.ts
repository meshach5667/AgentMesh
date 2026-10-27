import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { EarningsSummary } from '../types';

export const useEarnings = () =>
  useQuery({
    queryKey: ['earnings'],
    queryFn: async () => (await api.get<EarningsSummary>('/earnings')).data,
  });
