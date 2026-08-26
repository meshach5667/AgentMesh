import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import { Node } from '../types';

export const useNodes = () => {
  return useQuery({
    queryKey: ['nodes'],
    queryFn: async () => {
      const { data } = await api.get<Node[]>('/nodes');
      return data;
    },
  });
};

export const useNode = (id: string) => {
  return useQuery({
    queryKey: ['nodes', id],
    queryFn: async () => {
      const { data } = await api.get<Node>(`/nodes/\${id}`);
      return data;
    },
    enabled: !!id,
  });
};
