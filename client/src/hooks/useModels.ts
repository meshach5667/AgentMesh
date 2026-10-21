import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { Model } from '../types';

export const useModels = () =>
  useQuery({
    queryKey: ['models'],
    queryFn: async () => (await api.get<Model[]>('/models')).data,
  });

export const useModel = (id: string | null) =>
  useQuery({
    queryKey: ['models', id],
    queryFn: async () => (await api.get<Model>(`/models/${id}`)).data,
    enabled: !!id,
  });
