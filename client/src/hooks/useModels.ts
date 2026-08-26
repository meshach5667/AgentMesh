import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import { Model } from '../types';

export const useModels = () => {
  return useQuery({
    queryKey: ['models'],
    queryFn: async () => {
      const { data } = await api.get<Model[]>('/models');
      return data;
    },
  });
};
