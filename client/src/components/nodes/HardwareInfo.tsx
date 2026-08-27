import React from 'react';
import type { NodeHardware } from '../../types';
import { Card, CardContent } from '../ui/card';

export function HardwareInfo({ hardware }: { hardware?: NodeHardware }) {
  if (!hardware) return <p>No hardware info available</p>;
  
  return (
    <Card className="bg-gray-800">
      <CardContent className="pt-6 grid grid-cols-2 gap-4 text-sm">
        <div><span className="text-gray-400 block">CPU</span> {hardware.cpu_model} ({hardware.cpu_cores} Cores)</div>
        <div><span className="text-gray-400 block">RAM</span> {hardware.ram_gb} GB</div>
        <div><span className="text-gray-400 block">GPU</span> {hardware.gpu_model || 'None'} {hardware.gpu_vram_gb ? `(${hardware.gpu_vram_gb}GB)` : ''}</div>
        <div><span className="text-gray-400 block">Storage</span> {hardware.storage_gb} GB</div>
        <div className="col-span-2"><span className="text-gray-400 block">OS</span> {hardware.os_info}</div>
      </CardContent>
    </Card>
  );
}
