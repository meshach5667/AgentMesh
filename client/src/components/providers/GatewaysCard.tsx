'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Pill } from '@/components/common/StatusBadge';
import { useConnectGateway, useDisconnectGateway, useGateways } from '@/hooks/useCredits';
import { errorMessage } from '@/lib/errors';
import { dateTime } from '@/lib/format';
import { GATEWAY_LABEL, type GatewayName } from '@/types';

const KEY_HELP: Record<GatewayName, string> = {
  paystack: 'Secret key from Paystack → Settings → API Keys (sk_test_… or sk_live_…).',
  flutterwave: 'Secret key from Flutterwave → Settings → API Keys (FLWSECK_TEST-… or FLWSECK-…).',
  stripe: 'Secret or restricted key from Stripe → Developers → API keys (sk_… or rk_…), allowed to create Checkout Sessions.',
};

/** A provider's own gateway accounts: customers' payments there are verified automatically, money goes to them. */
export function GatewaysCard() {
  const gateways = useGateways();
  const connect = useConnectGateway();
  const disconnect = useDisconnectGateway();
  const [gateway, setGateway] = useState<GatewayName>('paystack');
  const [key, setKey] = useState('');
  const connected = new Map((gateways.data ?? []).map((g) => [g.gateway, g]));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Instant payment verification</CardTitle>
        <CardDescription>
          Connect your own Paystack, Flutterwave or Stripe account. Customers then pay you there and AgentMesh verifies
          each payment with your account in real time before your machines serve them. The money goes straight to you;
          AgentMesh never holds it and takes no fee. Your key is checked, stored encrypted, never shown again, and
          used only to start and verify payments to you.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {(gateways.data ?? []).length > 0 && (
          <ul className="divide-y divide-border text-sm">
            {(gateways.data ?? []).map((g) => (
              <li key={g.gateway} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="flex items-center gap-2">
                  {GATEWAY_LABEL[g.gateway]} <Pill tone={g.mode === 'live' ? 'green' : 'amber'}>{g.mode}</Pill>
                  <span className="font-mono text-xs text-muted-foreground">…{g.key_hint}</span>
                  <span className="text-xs text-muted-foreground">verified {dateTime(g.verified_at)}</span>
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={disconnect.isPending}
                  onClick={() =>
                    disconnect
                      .mutateAsync(g.gateway)
                      .then(() => toast.success(`${GATEWAY_LABEL[g.gateway]} disconnected`))
                      .catch((e) => toast.error(errorMessage(e)))
                  }
                >
                  Disconnect
                </Button>
              </li>
            ))}
          </ul>
        )}
        <form
          className="grid gap-3 sm:grid-cols-[10rem_1fr_auto] sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            connect
              .mutateAsync({ gateway, secret_key: key.trim() })
              .then(() => {
                setKey('');
                toast.success(`${GATEWAY_LABEL[gateway]} connected`);
              })
              .catch((err) => toast.error(errorMessage(err)));
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="gw-name">Gateway</Label>
            <select id="gw-name" className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" value={gateway} onChange={(e) => setGateway(e.target.value as GatewayName)}>
              {(Object.keys(GATEWAY_LABEL) as GatewayName[]).map((g) => (
                <option key={g} value={g}>
                  {GATEWAY_LABEL[g]}
                  {connected.has(g) ? ' (connected)' : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="gw-key">Secret key</Label>
            <Input id="gw-key" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} aria-describedby="gw-key-help" />
          </div>
          <Button type="submit" disabled={connect.isPending || key.trim().length < 16}>
            {connect.isPending ? 'Checking…' : connected.has(gateway) ? 'Replace key' : 'Connect'}
          </Button>
          <p id="gw-key-help" className="text-xs text-muted-foreground sm:col-span-3">
            {KEY_HELP[gateway]} Use a test key first to try it.
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
