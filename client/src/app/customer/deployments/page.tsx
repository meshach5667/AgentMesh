import { DeploymentCard } from '../../../components/deployments/DeploymentCard';
import { Button } from '../../../components/ui/Button';
import Link from 'next/link';
import type { Deployment } from '../../../types';

export default function CustomerDeployments() {
  const dummyDeps: Deployment[] = [
    {
      id: 'dep-123',
      status: 'RUNNING',
      model_id: 'llama3-8b',
      node_id: 'n1',
      customer_id: 'c1',
      config: {},
      started_at: new Date().toISOString(),
      ended_at: null,
      created_at: new Date().toISOString(),
      endpoint: null,
      model: { name: 'Llama 3 8B' },
    },
  ];
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">My Deployments</h1>
        <Link href="/customer/models">
          <Button>New Deployment</Button>
        </Link>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {dummyDeps.map((d) => (
          <DeploymentCard key={d.id} deployment={d} />
        ))}
      </div>
    </div>
  );
}
