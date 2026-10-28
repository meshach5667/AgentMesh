'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { ErrorState, PageHeader } from '@/components/common/Notices';
import { PageSkeleton } from '@/components/ui/Skeleton';
import { DefaultPricesCard } from '@/components/pricing/DefaultPricesCard';
import { PaymentArrangement } from '@/components/providers/PaymentArrangement';
import { useMyProviderProfile, useUpdateProviderProfile } from '@/hooks/useProviders';
import { safeExternalUrl } from '@/lib/billing';
import { errorMessage, fieldErrors } from '@/lib/errors';
import { PAYMENT_METHOD_LABEL, type PaymentLink, type PaymentMethod, type PaymentProfile, type ProviderCard } from '@/types';

const EMPTY: PaymentProfile = {
  methods: [],
  accepted_currencies: [],
  instructions: null,
  links: [],
  terms: null,
  minimum_amount: null,
  minimum_currency: null,
  minimum_note: null,
};

const SECRET_WORDS = /\b(pin|otp|one[- ]time (pass)?code|passcode|password|cvv|cvc|card number|seed phrase|private key)\b/i;

function validate(name: string, p: PaymentProfile, currencies: string): Record<string, string> {
  const errs: Record<string, string> = {};
  if (name.trim().length < 2) errs.display_name = 'Enter the name customers will see (at least 2 characters).';
  for (const field of ['instructions', 'terms', 'minimum_note'] as const) {
    if (p[field] && SECRET_WORDS.test(p[field]!)) errs[field] = 'Never ask customers for PINs, one-time codes, passwords or card details.';
  }
  p.links.forEach((l, i) => {
    if (!l.label.trim()) errs[`link-${i}`] = 'Give the link a label.';
    else if (!safeExternalUrl(l.url)) errs[`link-${i}`] = 'Use an https link to a public website, without a username or password.';
  });
  if (currencies.split(',').some((c) => c.trim() && !/^[A-Z]{3}$/.test(c.trim().toUpperCase())))
    errs.accepted_currencies = 'Use 3-letter codes separated by commas, such as NGN, USD.';
  if (p.minimum_amount && !/^\d+(\.\d{1,2})?$/.test(p.minimum_amount)) errs.minimum_amount = 'Use an amount like 5000 or 25.50.';
  return errs;
}

export default function ProviderPaymentsPage() {
  const profile = useMyProviderProfile();
  if (profile.isLoading) return <PageSkeleton />;
  if (profile.error || !profile.data) return <ErrorState message={errorMessage(profile.error)} retry={() => profile.refetch()} />;
  return <ProfileForm initial={profile.data} />;
}

function ProfileForm({ initial }: { initial: ProviderCard }) {
  const save = useUpdateProviderProfile();
  // A provider who never saved a profile gets the generated "Provider ab12cd34" name: start from an empty field.
  const [name, setName] = useState(initial.display_name.startsWith('Provider ') && !initial.payment ? '' : initial.display_name);
  const [description, setDescription] = useState(initial.description ?? '');
  const [payment, setPayment] = useState<PaymentProfile>(initial.payment ?? EMPTY);
  const [currencies, setCurrencies] = useState((initial.payment?.accepted_currencies ?? []).join(', '));
  const [submitted, setSubmitted] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  const errs = { ...validate(name, payment, currencies), ...serverErrors };
  const show = (k: string) => (submitted || serverErrors[k] ? errs[k] : undefined);
  const setP = <K extends keyof PaymentProfile>(k: K, v: PaymentProfile[K]) => setPayment((cur) => ({ ...cur, [k]: v }));
  const toggleMethod = (m: PaymentMethod) =>
    setP('methods', payment.methods.includes(m) ? payment.methods.filter((x) => x !== m) : [...payment.methods, m]);
  const setLink = (i: number, l: Partial<PaymentLink>) => setP('links', payment.links.map((x, j) => (j === i ? { ...x, ...l } : x)));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    setServerErrors({});
    if (Object.keys(validate(name, payment, currencies)).length) return;
    const body = {
      display_name: name.trim(),
      description: description.trim() || null,
      payment: {
        ...payment,
        accepted_currencies: currencies.split(',').map((c) => c.trim().toUpperCase()).filter(Boolean),
        instructions: payment.instructions?.trim() || null,
        terms: payment.terms?.trim() || null,
        minimum_note: payment.minimum_note?.trim() || null,
        minimum_amount: payment.minimum_amount || null,
        minimum_currency: payment.minimum_amount ? payment.minimum_currency || null : null,
      },
    };
    save
      .mutateAsync(body)
      .then(() => toast.success('Profile and payment arrangement saved'))
      .catch((err) => {
        setServerErrors(fieldErrors(err));
        toast.error(errorMessage(err));
      });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Profile & payment"
        description="How customers find you and pay you. Customers pay you directly; AgentMesh takes no fee and never handles the money."
      />
      <form onSubmit={submit} className="space-y-6" noValidate>
        <Card>
          <CardHeader>
            <CardTitle>Public profile</CardTitle>
            <CardDescription>Shown to signed-in customers on the providers page and on deployments that run on your machines.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="display_name">Name customers see</Label>
              <Input id="display_name" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} aria-invalid={!!show('display_name')} aria-describedby="display_name-err" />
              {show('display_name') && <p id="display_name-err" className="text-xs text-destructive">{show('display_name')}</p>}
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="description">What you offer (optional)</Label>
              <Textarea id="description" value={description} maxLength={500} rows={2} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Payment arrangement</CardTitle>
            <CardDescription>
              Tell customers how to pay you. Never ask for PINs, one-time codes, passwords or card details: AgentMesh
              rejects instructions that do.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Methods you accept</legend>
              <div className="flex flex-wrap gap-4">
                {(Object.keys(PAYMENT_METHOD_LABEL) as PaymentMethod[]).map((m) => (
                  <label key={m} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={payment.methods.includes(m)} onChange={() => toggleMethod(m)} />
                    {PAYMENT_METHOD_LABEL[m]}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="space-y-1.5">
              <Label htmlFor="accepted_currencies">Currencies you accept</Label>
              <Input id="accepted_currencies" value={currencies} placeholder="NGN, USD" onChange={(e) => setCurrencies(e.target.value)} aria-invalid={!!show('accepted_currencies')} />
              {show('accepted_currencies') && <p className="text-xs text-destructive">{show('accepted_currencies')}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="instructions">Payment instructions</Label>
              <Textarea
                id="instructions"
                rows={4}
                maxLength={2000}
                value={payment.instructions ?? ''}
                placeholder="For example: bank name, account name and number, and which reference to use."
                onChange={(e) => setP('instructions', e.target.value)}
                aria-invalid={!!show('instructions')}
              />
              {show('instructions') && <p className="text-xs text-destructive">{show('instructions')}</p>}
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Payment links (optional)</p>
              {payment.links.map((l, i) => (
                <div key={i} className="grid gap-2 sm:grid-cols-[12rem_1fr_auto]">
                  <Input aria-label={`Link ${i + 1} label`} value={l.label} maxLength={60} placeholder="Pay online" onChange={(e) => setLink(i, { label: e.target.value })} />
                  <Input aria-label={`Link ${i + 1} URL`} value={l.url} placeholder="https://" onChange={(e) => setLink(i, { url: e.target.value })} aria-invalid={!!show(`link-${i}`)} />
                  <Button type="button" variant="outline" onClick={() => setP('links', payment.links.filter((_, j) => j !== i))}>
                    Remove
                  </Button>
                  {show(`link-${i}`) && <p className="text-xs text-destructive sm:col-span-3">{show(`link-${i}`)}</p>}
                </div>
              ))}
              {payment.links.length < 5 && (
                <Button type="button" variant="outline" size="sm" onClick={() => setP('links', [...payment.links, { label: '', url: '' }])}>
                  Add a link
                </Button>
              )}
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="minimum_amount">Minimum amount (optional)</Label>
                <Input id="minimum_amount" inputMode="decimal" value={payment.minimum_amount ?? ''} onChange={(e) => setP('minimum_amount', e.target.value || null)} aria-invalid={!!show('minimum_amount')} />
                {show('minimum_amount') && <p className="text-xs text-destructive">{show('minimum_amount')}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="minimum_currency">Currency</Label>
                <Input id="minimum_currency" maxLength={3} value={payment.minimum_currency ?? ''} onChange={(e) => setP('minimum_currency', e.target.value.toUpperCase() || null)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="minimum_note">Minimum applies to</Label>
                <Input id="minimum_note" maxLength={200} value={payment.minimum_note ?? ''} placeholder="Per invoice" onChange={(e) => setP('minimum_note', e.target.value || null)} aria-invalid={!!show('minimum_note')} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="terms">Terms (optional)</Label>
              <Textarea id="terms" rows={3} maxLength={2000} value={payment.terms ?? ''} placeholder="When payment is due, and what happens if it is late." onChange={(e) => setP('terms', e.target.value)} aria-invalid={!!show('terms')} />
              {show('terms') && <p className="text-xs text-destructive">{show('terms')}</p>}
            </div>
          </CardContent>
        </Card>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save profile and payment arrangement'}
        </Button>
      </form>

      <Card>
        <CardHeader>
          <CardTitle>Preview</CardTitle>
          <CardDescription>What customers see on deployments that run on your machines.</CardDescription>
        </CardHeader>
        <CardContent>
          <PaymentArrangement payment={payment} providerName={name || 'You'} reference="AB12CD34" />
        </CardContent>
      </Card>

      <DefaultPricesCard />
    </div>
  );
}
