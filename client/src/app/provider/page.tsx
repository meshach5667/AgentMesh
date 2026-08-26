import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card';
import { EarningsChart } from '../../components/charts/EarningsChart';

export default function ProviderDashboard() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Provider Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card><CardHeader><CardTitle className="text-sm">Total Nodes</CardTitle></CardHeader><CardContent className="text-3xl font-bold">4</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Online Nodes</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-green-400">3</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Active Deployments</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-blue-400">12</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Total Earnings</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-green-500">$432.50</CardContent></Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Earnings History</CardTitle></CardHeader>
        <CardContent>
          <EarningsChart data={[{date: 'Mon', amount: 40}, {date: 'Tue', amount: 60}, {date: 'Wed', amount: 45}]} />
        </CardContent>
      </Card>
    </div>
  );
}
