import { TransactionList } from '../../../components/wallet/TransactionList';

export default function CustomerTransactions() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Transactions</h1>
      <TransactionList transactions={[]} />
    </div>
  );
}
