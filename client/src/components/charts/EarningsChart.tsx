'use client';
import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export interface EarningsDataPoint {
  date: string;
  amount: number;
  [key: string]: unknown;
}

export function EarningsChart({ data }: { data: EarningsDataPoint[] }) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <BarChart data={data}>
          <XAxis dataKey="date" stroke="#4b5563" />
          <YAxis stroke="#4b5563" />
          <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none' }} />
          <Bar dataKey="amount" fill="#10b981" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
