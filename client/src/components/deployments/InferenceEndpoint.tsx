'use client';
import React from 'react';
import { Copy } from 'lucide-react';
import { Button } from '../ui/button';

export function InferenceEndpoint({ url }: { url: string }) {
  const copy = () => navigator.clipboard.writeText(url);
  return (
    <div className="flex items-center gap-2 p-3 bg-gray-800 rounded-md border border-gray-700">
      <code className="text-sm text-green-400 flex-1 truncate">{url}</code>
      <Button variant="ghost" size="sm" onClick={copy}><Copy className="w-4 h-4" /></Button>
    </div>
  );
}
