'use client';

import { PageHeader } from '@/components/common/Notices';
import { LedgerHistory } from '@/components/wallet/LedgerHistory';

export default function CustomerTransactionsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Transactions" description="Every ledger entry involving your wallet: top-ups, charges, refunds and refunds to your card." />
      <LedgerHistory types={['DEPOSIT', 'COMPUTE_CHARGE', 'REFUND', 'TOPUP_REFUND']} />
    </div>
  );
}
