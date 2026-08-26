import React from 'react';
import type { Model } from '../../types';

export function ModelRequirements({ model }: { model: Model }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-800 rounded-lg text-sm">
      <div><span className="block text-gray-400 text-xs uppercase">Min VRAM</span>{model.minimum_vram} GB</div>
      <div><span className="block text-gray-400 text-xs uppercase">Min RAM</span>{model.minimum_ram} GB</div>
      <div><span className="block text-gray-400 text-xs uppercase">Min CPU</span>{model.minimum_cpu} Cores</div>
      <div><span className="block text-gray-400 text-xs uppercase">Storage</span>{model.storage_requirement} GB</div>
    </div>
  );
}
