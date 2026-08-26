import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card';
import { WalletBalance } from '../../components/wallet/WalletBalance';
import { formatCurrency } from '../../lib/utils';

export default function CustomerDashboard() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Customer Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card><CardHeader><CardTitle className="text-sm">Active Deployments</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-blue-400">2</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Total Spend</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-gray-300">{formatCurrency(150.75)}</CardContent></Card>
        <WalletBalance balance={450.25} currency="USD" />
      </div>
    </div>
  );
}
