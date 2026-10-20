'use client';

import { useParams } from 'next/navigation';
import { useDeployment, useStopDeployment } from '@/hooks/useDeployments';
import { InferenceEndpoint } from '@/components/deployments/InferenceEndpoint';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Spinner } from '@/components/ui/Spinner';
import { UsageChart } from '@/components/charts/UsageChart';
import { formatCurrency, formatDate } from '@/lib/utils';
import { Activity, Clock, DollarSign, Server, Square, RotateCcw } from 'lucide-react';
import toast from 'react-hot-toast';

const statusColors: Record<string, 'green' | 'yellow' | 'red' | 'blue' | 'orange'> = {
  READY: 'green', PROVISIONING: 'yellow', STARTING: 'yellow', UNHEALTHY: 'orange',
  STOPPED: 'red', CANCELLED: 'red', FAILED: 'orange', REQUESTED: 'blue', SCHEDULED: 'blue',
  STOPPING: 'red',
};

export default function DeploymentDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { data: deployment, isLoading, error } = useDeployment(id);
  const stopMutation = useStopDeployment();

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;
  if (error || !deployment) return <div className="text-red-400 text-center py-20">Failed to load deployment</div>;

  const handleStop = async () => {
    try {
      await stopMutation.mutateAsync(id);
      toast.success('Deployment stop requested');
    } catch {
      toast.error('Failed to stop deployment');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-white">Deployment Details</h1>
          <Badge color={statusColors[deployment.status] || 'blue'}>{deployment.status}</Badge>
        </div>
        <div className="flex gap-3">
          {deployment.status === 'READY' && (
            <>
              <Button variant="secondary" onClick={() => toast.success('Restart requested')}>
                <RotateCcw className="w-4 h-4 mr-2" />Restart
              </Button>
              <Button variant="destructive" onClick={handleStop} disabled={stopMutation.isPending}>
                <Square className="w-4 h-4 mr-2" />Stop
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="p-4">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1"><Activity className="w-4 h-4" />Status</div>
            <p className="text-lg font-semibold text-white">{deployment.status}</p>
          </div>
        </Card>
        <Card>
          <div className="p-4">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1"><Server className="w-4 h-4" />Model</div>
            <p className="text-lg font-semibold text-white">{deployment.model?.name || deployment.model_id}</p>
          </div>
        </Card>
        <Card>
          <div className="p-4">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1"><Clock className="w-4 h-4" />Started</div>
            <p className="text-lg font-semibold text-white">{deployment.started_at ? formatDate(deployment.started_at) : 'Pending'}</p>
          </div>
        </Card>
        <Card>
          <div className="p-4">
            <div className="flex items-center gap-2 text-gray-400 text-sm mb-1"><DollarSign className="w-4 h-4" />Cost</div>
            <p className="text-lg font-semibold text-white">{formatCurrency(deployment.total_cost || 0)}</p>
          </div>
        </Card>
      </div>

      {deployment.endpoint && deployment.status === 'READY' && (
        <Card>
          <div className="p-6">
            <h2 className="text-lg font-semibold text-white mb-3">Inference Endpoint</h2>
            <InferenceEndpoint url={deployment.endpoint} />
          </div>
        </Card>
      )}

      <Card>
        <div className="p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Usage Over Time</h2>
          <UsageChart data={[]} />
        </div>
      </Card>

      <Card>
        <div className="p-6">
          <h2 className="text-lg font-semibold text-white mb-3">Configuration</h2>
          <pre className="bg-gray-900 rounded p-4 text-sm text-gray-300 overflow-auto">
            {JSON.stringify(deployment.config || {}, null, 2)}
          </pre>
        </div>
      </Card>
    </div>
  );
}
