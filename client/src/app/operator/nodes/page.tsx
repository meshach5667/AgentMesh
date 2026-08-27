import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../../components/ui/table';
import { NodeStatusBadge } from '../../../components/nodes/NodeStatusBadge';
import type { NodeStatus } from '../../../types';

interface DummyNode {
  id: string;
  name: string;
  status: NodeStatus;
  region: string;
  owner_id: string;
}

export default function OperatorNodes() {
  const dummyNodes: DummyNode[] = [
    { id: 'n1', name: 'Node 1', status: 'ONLINE', region: 'US', owner_id: 'provider1' },
  ];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">All Nodes Registry</h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Owner</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {dummyNodes.map((n) => (
            <TableRow key={n.id}>
              <TableCell>{n.id}</TableCell>
              <TableCell>{n.name}</TableCell>
              <TableCell>{n.owner_id}</TableCell>
              <TableCell>
                <NodeStatusBadge status={n.status} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
