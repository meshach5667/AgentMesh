import { EarningsChart } from '../../../components/charts/EarningsChart';
import { Card, CardHeader, CardTitle, CardContent } from '../../../components/ui/Card';
import { formatCurrency } from '../../../lib/utils';

export default function EarningsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Earnings</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card><CardHeader><CardTitle className="text-sm">Total Earnings</CardTitle></CardHeader><CardContent className="text-3xl font-bold">{formatCurrency(1250)}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Pending Payout</CardTitle></CardHeader><CardContent className="text-3xl font-bold">{formatCurrency(250)}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Available Balance</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-green-500">{formatCurrency(1000)}</CardContent></Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Earnings History</CardTitle></CardHeader>
        <CardContent><EarningsChart data={[]} /></CardContent>
      </Card>
    </div>
  );
}
