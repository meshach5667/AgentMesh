'use client';

import { PageHeader } from '@/components/common/Notices';
import { LedgerHistory } from '@/components/wallet/LedgerHistory';

export default function ProviderTransactionsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Ledger" description="Every ledger entry involving your wallet: earnings, payouts, and your share of refunded charges." />
      <LedgerHistory types={['PROVIDER_CREDIT', 'PAYOUT', 'REFUND_CLAWBACK', 'DEPOSIT']} />
    </div>
  );
}
