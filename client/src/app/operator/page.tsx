import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { formatCurrency } from '../../lib/utils';

export default function OperatorDashboard() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Network Operator Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card><CardHeader><CardTitle className="text-sm">Total Nodes</CardTitle></CardHeader><CardContent className="text-3xl font-bold">142</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Active Deployments</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-blue-400">89</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Network Revenue</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-green-500">{formatCurrency(45200)}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-sm">Platform Fees</CardTitle></CardHeader><CardContent className="text-3xl font-bold text-yellow-500">{formatCurrency(4520)}</CardContent></Card>
      </div>
    </div>
  );
}
