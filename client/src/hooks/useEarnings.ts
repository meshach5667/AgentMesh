import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';

export interface EarningsData {
  pending_earnings: number;
  available_balance: number;
  total_earned: number;
}

export interface PayoutRecord {
  id: string;
  date: string;
  amount: number;
  status: string;
  type: string;
}

export const useEarnings = () => {
  return useQuery({
    queryKey: ['earnings'],
    queryFn: async () => {
      // Assuming a generic /earnings endpoint for overview
      try {
        const { data } = await api.get<EarningsData>('/earnings');
        return data;
      } catch (error) {
        // Fallback for UI if endpoint doesn't exist yet
        console.warn('API /earnings not ready, falling back');
        return {
          pending_earnings: 0,
          available_balance: 0,
          total_earned: 0,
        };
      }
    },
  });
};

export const usePayoutHistory = () => {
  return useQuery({
    queryKey: ['earnings-history'],
    queryFn: async () => {
      try {
        const { data } = await api.get<PayoutRecord[]>('/earnings/history');
        return data;
      } catch (error) {
        return [];
      }
    },
  });
};
