import Link from 'next/link';
import { Button } from '../../../components/ui/Button';
import { NodeCard } from '../../../components/nodes/NodeCard';
import type { Node } from '../../../types';

export default function ProviderNodes() {
  const dummyNodes: Node[] = [
    {
      id: '1',
      name: 'Alpha GPU Node',
      status: 'ONLINE',
      region: 'US-East',
      reputation_score: 98,
      owner_id: 'x',
      last_heartbeat: '',
      created_at: '',
      hardware: {
        cpu_model: 'Intel Core i9',
        cpu_cores: 16,
        ram_gb: 64,
        storage_gb: 1000,
        gpu_model: 'RTX 4090',
        gpu_count: 1,
        gpu_vram_gb: 24,
        os_info: 'Linux',
      },
    },
  ];
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">My Nodes</h1>
        <Link href="/provider/nodes/register">
          <Button>Register New Node</Button>
        </Link>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {dummyNodes.map((n) => (
          <NodeCard key={n.id} node={n} />
        ))}
      </div>
    </div>
  );
}
