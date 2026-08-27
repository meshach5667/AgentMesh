'use client';
import React from 'react';
import { Button } from '../ui/button';

export function DeploymentForm({ modelId, onSubmit }: { modelId: string, onSubmit: () => void }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-300">Ready to deploy model: {modelId}</p>
      <Button onClick={onSubmit}>Deploy Now</Button>
    </div>
  );
}
