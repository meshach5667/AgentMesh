'use client';
import { DeploymentForm } from '../../../../components/deployments/DeploymentForm';
import { useSearchParams } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '../../../../components/ui/Card';

export default function NewDeployment() {
  const searchParams = useSearchParams();
  const modelId = searchParams.get('model') || 'unknown';

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Deploy Model</h1>
      <Card>
        <CardHeader><CardTitle>Configure Deployment</CardTitle></CardHeader>
        <CardContent>
          <DeploymentForm modelId={modelId} onSubmit={() => alert('Deploying...')} />
        </CardContent>
      </Card>
    </div>
  );
}
