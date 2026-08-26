import { TransactionList } from '../../../components/wallet/TransactionList';

export default function OperatorTransactions() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">All Network Transactions</h1>
      <TransactionList transactions={[]} />
    </div>
  );
}
