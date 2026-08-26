import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { NodeStatusBadge } from './NodeStatusBadge';
import type { Node } from '../../types';

export function NodeCard({ node }: { node: Node }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle>{node.name}</CardTitle>
        <NodeStatusBadge status={node.status} />
      </CardHeader>
      <CardContent>
        <div className="text-sm text-gray-400 space-y-2">
          <p>Region: {node.region}</p>
          <p>GPU: {node.hardware?.gpu_model || 'None'}</p>
          <p>CPU: {node.hardware?.cpu_model}</p>
          <p>Score: {node.reputation_score}/100</p>
        </div>
      </CardContent>
    </Card>
  );
}
