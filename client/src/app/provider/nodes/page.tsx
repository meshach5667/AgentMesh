import Link from 'next/link';
import { Button } from '../../../components/ui/Button';
import { NodeCard } from '../../../components/nodes/NodeCard';

export default function ProviderNodes() {
  const dummyNodes = [
    { id: '1', name: 'Alpha GPU Node', status: 'ONLINE', region: 'US-East', reputation_score: 98, owner_id: 'x', last_heartbeat: '', created_at: '', hardware: { gpu_model: 'RTX 4090' } },
  ];
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">My Nodes</h1>
        <Link href="/provider/nodes/register"><Button>Register New Node</Button></Link>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {dummyNodes.map(n => <NodeCard key={n.id} node={n as any} />)}
      </div>
    </div>
  );
}
