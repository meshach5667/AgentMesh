import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';

export interface TransactionRecord {
  id: string;
  date: string;
  type: string;
  node?: string;
  deployment?: string;
  amount: number;
  status: string;
}

export const useTransactions = () => {
  return useQuery({
    queryKey: ['transactions'],
    queryFn: async () => {
      try {
        const { data } = await api.get<TransactionRecord[]>('/transactions');
        return data;
      } catch (error) {
        return [];
      }
    },
  });
};
