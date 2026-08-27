'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export default function ProviderSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Manage your provider account and node preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Payout Information</CardTitle>
          <CardDescription>Configure how you receive your earnings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 max-w-md">
          <div className="space-y-2">
            <label className="text-sm font-medium">Payout Method</label>
            <Input defaultValue="Stripe Connect" disabled />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Connected Account</label>
            <Input defaultValue="acct_1032D82..." disabled />
          </div>
          <Button variant="outline">Manage Payouts</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Node Agent Keys</CardTitle>
          <CardDescription>Manage authentication keys for your compute nodes.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="bg-secondary/20 p-4 rounded-md border border-border flex justify-between items-center mb-4">
            <div>
              <p className="font-mono text-sm">node_key_a7b2...9f1e</p>
              <p className="text-xs text-muted-foreground">Active on 3 nodes</p>
            </div>
            <Button variant="destructive" size="sm">Revoke</Button>
          </div>
          <Button variant="outline">Generate New Node Key</Button>
        </CardContent>
      </Card>
    </div>
  );
}
