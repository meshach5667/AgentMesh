export type TransactionType = 'DEPOSIT' | 'COMPUTE_CHARGE' | 'PROVIDER_CREDIT' | 'PLATFORM_FEE' | 'REFUND' | 'PAYOUT';
export type TransactionStatus = 'PENDING' | 'AUTHORIZED' | 'SETTLED' | 'REFUNDED' | 'FAILED';

export interface Wallet {
  id: string;
  user_id: string;
  balance: number;
  currency: string;
}

export interface Transaction {
  id: string;
  from_wallet: string | null;
  to_wallet: string | null;
  amount: number;
  type: TransactionType;
  status: TransactionStatus;
  deployment_id: string | null;
  reference: string;
  description: string;
  created_at: string;
}
