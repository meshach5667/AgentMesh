'use client';
import React from 'react';

export function MetricsGauge({ value, label }: { value: number, label: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-4 bg-gray-800 rounded-full w-32 h-32 border-4 border-blue-500/20">
      <span className="text-2xl font-bold text-white">{value}%</span>
      <span className="text-xs text-gray-400 uppercase">{label}</span>
    </div>
  );
}
