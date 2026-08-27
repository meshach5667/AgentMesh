'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export default function CustomerSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Manage your account preferences and API keys.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile Details</CardTitle>
          <CardDescription>Update your personal information.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 max-w-md">
          <div className="space-y-2">
            <label className="text-sm font-medium">Email Address</label>
            <Input defaultValue="customer@example.com" disabled />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Display Name</label>
            <Input placeholder="Enter your name" />
          </div>
          <Button>Save Changes</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
          <CardDescription>Manage keys used for programmatic access to AgentMesh.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="bg-secondary/20 p-4 rounded-md border border-border flex justify-between items-center mb-4">
            <div>
              <p className="font-mono text-sm">am_live_8f92a1...4x9b</p>
              <p className="text-xs text-muted-foreground">Created on Mar 1, 2024</p>
            </div>
            <Button variant="destructive" size="sm">Revoke</Button>
          </div>
          <Button variant="outline">Generate New Key</Button>
        </CardContent>
      </Card>
    </div>
  );
}
