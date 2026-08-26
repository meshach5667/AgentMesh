import React from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../ui/Card';
import { Button } from '../ui/Button';
import type { Model } from '../../types';
import Link from 'next/link';

export function ModelCard({ model }: { model: Model }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{model.name}</CardTitle>
        <p className="text-xs text-gray-400">v{model.version} • {model.runtime}</p>
      </CardHeader>
      <CardContent>
        <div className="text-sm space-y-1 text-gray-300">
          <p>VRAM: {model.minimum_vram} GB</p>
          <p>RAM: {model.minimum_ram} GB</p>
        </div>
      </CardContent>
      <CardFooter>
        <Link href={\`/customer/deployments/new?model=\${model.id}\`} className="w-full">
          <Button className="w-full">Deploy</Button>
        </Link>
      </CardFooter>
    </Card>
  );
}
