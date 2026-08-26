import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../../components/ui/Table';
import { NodeStatusBadge } from '../../../components/nodes/NodeStatusBadge';

export default function OperatorDeployments() {
  const dummyDeps = [{ id: 'd1', model_id: 'm1', customer_id: 'c1', node_id: 'n1', status: 'RUNNING' }];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">All Deployments</h1>
      <Table>
        <TableHeader><TableRow><TableHead>ID</TableHead><TableHead>Customer</TableHead><TableHead>Model</TableHead><TableHead>Node</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
        <TableBody>
          {dummyDeps.map(d => (
            <TableRow key={d.id}><TableCell>{d.id}</TableCell><TableCell>{d.customer_id}</TableCell><TableCell>{d.model_id}</TableCell><TableCell>{d.node_id}</TableCell><TableCell><NodeStatusBadge status={d.status as any} /></TableCell></TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
