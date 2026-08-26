'use client';
import { WalletBalance } from '../../../components/wallet/WalletBalance';
import { DepositForm } from '../../../components/wallet/DepositForm';
import { TransactionList } from '../../../components/wallet/TransactionList';

export default function CustomerWallet() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Wallet</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <WalletBalance balance={450.25} currency="USD" />
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Add Funds</h2>
          <DepositForm onDeposit={(a) => alert('Depositing ' + a)} />
        </div>
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-4">Recent Transactions</h2>
        <TransactionList transactions={[]} />
      </div>
    </div>
  );
}
