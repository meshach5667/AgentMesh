import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { Transaction, TransactionType } from '../types';

export interface LedgerFilter {
  types?: TransactionType[];
  limit?: number;
  offset?: number;
}

/** FastAPI reads a repeated query parameter (?type=A&type=B) as a list. */
export function ledgerParams({ types, limit, offset }: LedgerFilter = {}): URLSearchParams {
  const params = new URLSearchParams();
  for (const t of types ?? []) params.append('type', t);
  if (limit) params.set('limit', String(limit));
  if (offset) params.set('offset', String(offset));
  return params;
}

export const useTransactions = (filter: LedgerFilter = {}) =>
  useQuery({
    queryKey: ['transactions', filter],
    queryFn: async () => (await api.get<Transaction[]>('/transactions', { params: ledgerParams(filter) })).data,
  });

/** Download the caller's ledger (with the same type filter) as CSV. */
export async function downloadLedgerCsv(filter: LedgerFilter = {}): Promise<void> {
  const resp = await api.get<Blob>('/transactions/export.csv', { params: ledgerParams(filter), responseType: 'blob' });
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'agentmesh-transactions.csv';
  a.click();
  URL.revokeObjectURL(url);
}
