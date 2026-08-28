'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Server, Cpu } from 'lucide-react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

export default function MarketplacePage() {
  const providers = [
    { id: '1', name: 'Node-7x9a', gpu: '1x RTX 4090', vram: '24 GB', price: '$0.25/hr', status: 'Available', uptime: '99.9%' },
    { id: '2', name: 'US-East-Alpha', gpu: '4x A100', vram: '320 GB', price: '$4.10/hr', status: 'Available', uptime: '99.99%' },
    { id: '3', name: 'Desk-Node-02', gpu: '1x RTX 3090', vram: '24 GB', price: '$0.18/hr', status: 'Busy', uptime: '97.5%' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Marketplace</h1>
        <p className="text-muted-foreground">Explore available compute nodes in the AgentMesh network.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Open Compute Network</CardTitle>
          <CardDescription>Live view of available nodes and their pricing.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider / Node</TableHead>
                <TableHead>Hardware</TableHead>
                <TableHead>VRAM</TableHead>
                <TableHead>Reliability</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Price</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {providers.map((p, i) => (
                <TableRow key={i}>
                  <TableCell className="flex items-center gap-3">
                    <Server className="w-4 h-4 text-muted-foreground" />
                    {p.name}
                  </TableCell>
                  <TableCell>{p.gpu}</TableCell>
                  <TableCell>{p.vram}</TableCell>
                  <TableCell>{p.uptime}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={p.status === 'Available' ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-amber-500/10 text-amber-500 border-amber-500/20'}>
                      {p.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-bold text-foreground">
                    {p.price}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
