import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { NodeStatusBadge } from '../nodes/NodeStatusBadge';
import type { Deployment } from '../../types';
import Link from 'next/link';

export function DeploymentCard({ deployment }: { deployment: Deployment }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base truncate">{deployment.id}</CardTitle>
        <NodeStatusBadge status={deployment.status as any} />
      </CardHeader>
      <CardContent>
        <div className="text-sm text-gray-400 space-y-1 mb-4">
          <p>Model: {deployment.model?.name || deployment.model_id}</p>
          <p>Started: {deployment.started_at ? new Date(deployment.started_at).toLocaleString() : 'N/A'}</p>
        </div>
        <Link href={\`/customer/deployments/\${deployment.id}\`} className="text-blue-500 hover:underline text-sm">
          View Details
        </Link>
      </CardContent>
    </Card>
  );
}
