'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ErrorState, Notice, PageHeader } from '@/components/common/Notices';
import { Pill } from '@/components/common/StatusBadge';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { PaymentArrangement } from '@/components/providers/PaymentArrangement';
import { useCredits, useStartTopup, useVerifyTopup } from '@/hooks/useCredits';
import { useOffers, useProvider } from '@/hooks/useProviders';
import { isGatewayCheckout } from '@/lib/billing';
import { errorMessage } from '@/lib/errors';
import { dateTime, money } from '@/lib/format';
import { GATEWAY_LABEL, type CreditPaymentState, type GatewayName } from '@/types';

const STATE_TONE: Record<CreditPaymentState, 'green' | 'amber' | 'red' | 'gray'> = {
  PENDING: 'amber',
  VERIFIED: 'green',
  FAILED: 'red',
  REJECTED: 'red',
  REVIEW: 'amber',
};
const STATE_TEXT: Record<CreditPaymentState, string> = {
  PENDING: 'Waiting for verification',
  VERIFIED: 'Verified and credited',
  FAILED: 'Failed',
  REJECTED: 'Rejected by the provider',
  REVIEW: 'Held for review',
};

export default function CustomerCreditsPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Credits />
    </Suspense>
  );
}

function Credits() {
  const params = useSearchParams();
  const credits = useCredits();
  const verify = useVerifyTopup();
  const checked = useRef(false);
  const returned = params.get('payment');

  // Back from a provider's gateway checkout: verify with the provider's gateway right away.
  useEffect(() => {
    if (!returned || checked.current || !/^[0-9a-f-]{36}$/.test(returned)) return;
    checked.current = true;
    verify
      .mutateAsync(returned)
      .then((p) =>
        p.state === 'VERIFIED'
          ? toast.success('Payment verified and credited')
          : p.state === 'PENDING'
            ? toast('Payment not confirmed by the gateway yet; it is checked again automatically')
            : toast.error(`Payment ${STATE_TEXT[p.state].toLowerCase()}`),
      )
      .catch((e) => toast.error(errorMessage(e)));
  }, [returned, verify]);

  if (credits.isLoading) return <PageSkeleton />;
  if (credits.error) return <ErrorState message={errorMessage(credits.error)} retry={() => credits.refetch()} />;
  const data = credits.data!;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Prepaid credit"
        description="Priced machines run your deployments only while you hold verified credit with their provider. You pay the provider directly; AgentMesh verifies the payment and never holds your money."
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.balances.length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">Credit</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">No credit yet. Free machines need none.</CardContent>
          </Card>
        ) : (
          data.balances.map((b) => (
            <Card key={`${b.provider_id}-${b.currency}`}>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">With {b.provider}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className={`text-2xl font-semibold tabular-nums ${Number(b.balance) <= 0 ? 'text-destructive' : ''}`}>
                  {money(b.balance, b.currency)}
                </p>
              </CardContent>
            </Card>
          ))
        )}
      </div>
      <BuyCredit />
      <Card>
        <CardHeader>
          <CardTitle>Payments</CardTitle>
        </CardHeader>
        <CardContent>
          {data.payments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No payments yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>Reference</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.payments.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="text-xs">{dateTime(p.created_at)}</TableCell>
                      <TableCell className="text-xs">{p.method === 'gateway' && p.gateway ? GATEWAY_LABEL[p.gateway] : 'Transfer (provider confirms)'}</TableCell>
                      <TableCell className="font-mono text-xs">{p.reference}</TableCell>
                      <TableCell className="text-right tabular-nums">{money(p.amount, p.currency)}</TableCell>
                      <TableCell>
                        <Pill tone={STATE_TONE[p.state]}>{STATE_TEXT[p.state]}</Pill>
                        {p.reason && <span className="block text-xs text-muted-foreground">{p.reason}</span>}
                      </TableCell>
                      <TableCell className="text-right">
                        {p.state === 'PENDING' && p.method === 'gateway' && (
                          <div className="flex justify-end gap-1">
                            {isGatewayCheckout(p.checkout_url) && (
                              <a href={p.checkout_url} className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted">
                                Continue payment
                              </a>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={verify.isPending}
                              onClick={() => verify.mutateAsync(p.id).then((r) => toast(STATE_TEXT[r.state])).catch((e) => toast.error(errorMessage(e)))}
                            >
                              Check now
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BuyCredit() {
  const offers = useOffers();
  const start = useStartTopup();
  const [providerId, setProviderId] = useState('');
  const provider = useProvider(providerId || null);
  const [amount, setAmount] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [method, setMethod] = useState<'gateway' | 'manual'>('gateway');
  const [gateway, setGateway] = useState<GatewayName | ''>('');
  const [reference, setReference] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const gateways = provider.data?.gateways ?? [];
  const manualOk = !!provider.data?.accepts_payment_arrangement;
  const chosenGateway = gateway || gateways[0] || '';
  const errors = {
    provider: providerId ? null : 'Choose a provider.',
    amount: /^\d+(\.\d{1,2})?$/.test(amount.trim()) && Number(amount) > 0 ? null : 'Enter an amount such as 5000 or 25.50.',
    currency: /^[A-Z]{3}$/.test(currency) ? null : 'Use a 3-letter currency code.',
    method: method === 'gateway' ? (chosenGateway ? null : 'This provider has not connected a gateway; pay by transfer.') : manualOk ? null : 'This provider has not published how to be paid by transfer.',
    reference: method === 'manual' && reference.trim().length < 3 ? 'Give the reference of your transfer.' : null,
  };
  const valid = Object.values(errors).every((e) => !e);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    if (!valid) return;
    start
      .mutateAsync({
        provider_id: providerId,
        amount: amount.trim(),
        currency,
        method,
        ...(method === 'gateway' ? { gateway: chosenGateway as GatewayName } : { reference: reference.trim() }),
      })
      .then((p) => {
        if (p.method === 'gateway') {
          if (isGatewayCheckout(p.checkout_url)) window.location.assign(p.checkout_url);
          else toast.error('The gateway did not return a checkout page');
        } else {
          toast.success('Recorded. Your credit is added as soon as the provider confirms the transfer.');
          setReference('');
        }
      })
      .catch((err) => toast.error(errorMessage(err)));
  };
  const err = (k: keyof typeof errors) =>
    submitted && errors[k] ? <p className="text-xs text-destructive">{errors[k]}</p> : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Buy credit</CardTitle>
        <CardDescription>
          Pay a provider directly. Gateway payments are verified with the provider&apos;s own gateway account the
          moment you return; transfers are credited when the provider confirms receiving them.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="credit-provider">Provider</Label>
              <select id="credit-provider" className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" value={providerId} onChange={(e) => (setProviderId(e.target.value), setGateway(''))}>
                <option value="">Choose…</option>
                {(offers.data ?? []).map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.display_name}
                  </option>
                ))}
              </select>
              {err('provider')}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="credit-amount">Amount</Label>
              <Input id="credit-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} aria-invalid={submitted && !!errors.amount} />
              {err('amount')}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="credit-currency">Currency</Label>
              <Input id="credit-currency" maxLength={3} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} aria-invalid={submitted && !!errors.currency} />
              {err('currency')}
            </div>
          </div>
          {providerId && (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">How you pay</legend>
              <label className="flex items-start gap-2 text-sm">
                <input type="radio" name="credit-method" className="mt-1" checked={method === 'gateway'} onChange={() => setMethod('gateway')} disabled={gateways.length === 0} />
                <span>
                  Pay online, verified instantly
                  <span className="block text-xs text-muted-foreground">
                    {gateways.length ? `Through ${gateways.map((g) => GATEWAY_LABEL[g]).join(' or ')} (the provider's own account)` : 'This provider has not connected a gateway'}
                  </span>
                </span>
              </label>
              {method === 'gateway' && gateways.length > 1 && (
                <select aria-label="Gateway" className="ml-6 h-9 rounded-md border border-input bg-transparent px-3 text-sm" value={chosenGateway} onChange={(e) => setGateway(e.target.value as GatewayName)}>
                  {gateways.map((g) => (
                    <option key={g} value={g}>
                      {GATEWAY_LABEL[g]}
                    </option>
                  ))}
                </select>
              )}
              <label className="flex items-start gap-2 text-sm">
                <input type="radio" name="credit-method" className="mt-1" checked={method === 'manual'} onChange={() => setMethod('manual')} disabled={!manualOk} />
                <span>
                  I paid by transfer; the provider confirms it
                  <span className="block text-xs text-muted-foreground">{manualOk ? 'Credited when the provider confirms receiving it' : 'Not offered by this provider'}</span>
                </span>
              </label>
              {err('method')}
            </fieldset>
          )}
          {providerId && method === 'manual' && provider.data && (
            <div className="space-y-3 rounded-lg border border-border p-4">
              <PaymentArrangement payment={provider.data.payment} providerName={provider.data.display_name} />
              <div className="space-y-1.5">
                <Label htmlFor="credit-reference">Reference of your transfer</Label>
                <Input id="credit-reference" maxLength={100} value={reference} onChange={(e) => setReference(e.target.value)} aria-invalid={submitted && !!errors.reference} />
                {err('reference')}
              </div>
            </div>
          )}
          <Notice tone="info" title="Never share secrets">
            AgentMesh and providers will never ask for your card PIN, one-time codes or banking passwords.
          </Notice>
          <Button type="submit" disabled={start.isPending}>
            {start.isPending ? 'Starting…' : method === 'gateway' ? 'Continue to payment' : 'Record my transfer'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
