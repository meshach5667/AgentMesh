'use client';
import React from 'react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import type { NodePricing } from '../../types';

export function PricingForm({
  pricing,
  onSave,
}: {
  pricing?: NodePricing;
  onSave: (p: Partial<NodePricing>) => void;
}) {
  const [data, setData] = React.useState<Partial<NodePricing>>(
    pricing || {
      gpu_hour_price: 0,
      cpu_hour_price: 0,
      ram_gb_hour_price: 0,
    }
  );

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm">GPU Price ($/hr)</label>
        <Input
          type="number"
          value={data.gpu_hour_price ?? 0}
          onChange={(e) =>
            setData({ ...data, gpu_hour_price: +e.target.value })
          }
        />
      </div>
      <div>
        <label className="text-sm">CPU Price ($/hr)</label>
        <Input
          type="number"
          value={data.cpu_hour_price ?? 0}
          onChange={(e) =>
            setData({ ...data, cpu_hour_price: +e.target.value })
          }
        />
      </div>
      <Button onClick={() => onSave(data)}>Save Pricing</Button>
    </div>
  );
}
