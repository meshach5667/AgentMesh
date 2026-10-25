'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState, ErrorState, PageHeader } from '@/components/common/Notices';
import { TableSkeleton } from '@/components/ui/Skeleton';
import { useAdSettings, useCampaigns, useSaveCampaign, useSetCampaignStatus, useUpdateAdSettings } from '@/hooks/useSponsorship';
import { errorMessage } from '@/lib/errors';
import { dateTime, money } from '@/lib/format';
import { CATEGORY_LABEL, pricingLabel } from '@/lib/sponsorship';
import { usePaymentsConfig } from '@/hooks/useBilling';
import type { AdSettings, Campaign, CampaignInput, CampaignStatus, Placement, SponsorCategory, SponsorPricingModel } from '@/types';

const SELECT = 'h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm';

/** Moves an operator can make from each status; "ended" is final (mirrors ALLOWED_STATUS on the server). */
const NEXT: Record<CampaignStatus, { to: CampaignStatus; label: string }[]> = {
  draft: [
    { to: 'active', label: 'Activate' },
    { to: 'ended', label: 'End' },
  ],
  active: [
    { to: 'paused', label: 'Pause' },
    { to: 'ended', label: 'End' },
  ],
  paused: [
    { to: 'active', label: 'Resume' },
    { to: 'ended', label: 'End' },
  ],
  ended: [],
};

function SettingsCard({ settings }: { settings: AdSettings }) {
  const update = useUpdateAdSettings();
  const [slots, setSlots] = useState(() => Object.fromEntries(settings.placements.map((p) => [p.key, { enabled: p.enabled, max_items: p.max_items }])));
  const save = (body: Parameters<typeof update.mutate>[0], done: string) =>
    update.mutate(body, { onSuccess: () => toast.success(done), onError: (err) => toast.error(errorMessage(err)) });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Advertising</CardTitle>
        <CardDescription>
          Off by default. While off, no sponsored item is served anywhere. Each placement can also be switched off on its own; items are always labelled
          &ldquo;Sponsored&rdquo; and viewers can dismiss them.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-sm">
            Status: <strong>{settings.enabled ? 'On' : 'Off'}</strong>
          </span>
          <Button size="sm" variant={settings.enabled ? 'outline' : 'default'} disabled={update.isPending} onClick={() => save({ enabled: !settings.enabled }, settings.enabled ? 'Advertising turned off' : 'Advertising turned on')}>
            {settings.enabled ? 'Turn off' : 'Turn on'}
          </Button>
          <span className="text-xs text-muted-foreground">Last changed {dateTime(settings.updated_at)}</span>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Placement</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead>Items shown (1–3)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {settings.placements.map((p) => (
              <TableRow key={p.key}>
                <TableCell className="text-sm">{p.label}</TableCell>
                <TableCell>
                  <input
                    type="checkbox"
                    aria-label={`Show sponsored items on ${p.label}`}
                    checked={slots[p.key]?.enabled ?? false}
                    onChange={(e) => setSlots((s) => ({ ...s, [p.key]: { ...s[p.key], enabled: e.target.checked } }))}
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    min={1}
                    max={3}
                    aria-label={`Items shown on ${p.label}`}
                    className="w-20"
                    value={slots[p.key]?.max_items ?? 1}
                    onChange={(e) => setSlots((s) => ({ ...s, [p.key]: { ...s[p.key], max_items: Math.min(3, Math.max(1, Number(e.target.value) || 1)) } }))}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Button size="sm" variant="outline" disabled={update.isPending} onClick={() => save({ placements: slots }, 'Placements saved')}>
          Save placements
        </Button>
      </CardContent>
    </Card>
  );
}

const EMPTY: CampaignInput = {
  name: '',
  sponsor: '',
  category: 'ai_tools',
  headline: '',
  body: '',
  cta_label: 'Learn more',
  target_url: 'https://',
  image_url: '',
  placements: ['customer_dashboard'],
  starts_at: '',
  ends_at: '',
  weight: 1,
  pricing_model: 'cpm',
  rate: '',
  budget: '',
};

/** datetime-local value (local time, minutes) from an ISO timestamp, and back to ISO (UTC) for the API. */
const toLocal = (iso: string | null | undefined) => (iso ? new Date(iso).toISOString().slice(0, 16) : '');
const toIso = (local: string | null | undefined) => (local ? new Date(local + 'Z').toISOString() : null);

function fromCampaign(c: Campaign): CampaignInput {
  return { ...c, body: c.body ?? '', image_url: c.image_url ?? '', budget: c.budget ?? '', starts_at: toLocal(c.starts_at), ends_at: toLocal(c.ends_at) };
}

function CampaignForm({ editing, placements, currency, onDone }: { editing: Campaign | null; placements: AdSettings['placements']; currency: string; onDone: () => void }) {
  const save = useSaveCampaign();
  const [form, setForm] = useState<CampaignInput>(() => (editing ? fromCampaign(editing) : EMPTY));
  const set = <K extends keyof CampaignInput>(key: K, value: CampaignInput[K]) => setForm((f) => ({ ...f, [key]: value }));
  const field = (key: 'name' | 'sponsor' | 'headline' | 'cta_label' | 'target_url' | 'image_url', label: string, props: React.ComponentProps<typeof Input> = {}) => (
    <div className="space-y-1">
      <label htmlFor={`c-${key}`} className="text-xs text-muted-foreground">
        {label}
      </label>
      <Input id={`c-${key}`} value={form[key] ?? ''} onChange={(e) => set(key, e.target.value)} {...props} />
    </div>
  );

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        const body: CampaignInput = {
          ...form,
          body: form.body?.trim() || null,
          image_url: form.image_url?.trim() || null,
          budget: form.budget?.trim() || null,
          starts_at: toIso(form.starts_at),
          ends_at: toIso(form.ends_at),
        };
        save.mutate(
          { id: editing?.id, body },
          {
            onSuccess: () => {
              toast.success(editing ? 'Campaign updated' : 'Campaign created as a draft');
              onDone();
            },
            onError: (err) => toast.error(errorMessage(err)),
          },
        );
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {field('name', 'Internal name', { required: true, minLength: 2, maxLength: 100 })}
        {field('sponsor', 'Sponsor (shown)', { required: true, minLength: 2, maxLength: 60 })}
        <div className="space-y-1">
          <label htmlFor="c-category" className="text-xs text-muted-foreground">
            Category
          </label>
          <select id="c-category" className={SELECT} value={form.category} onChange={(e) => set('category', e.target.value as SponsorCategory)}>
            {Object.entries(CATEGORY_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        {field('headline', 'Headline', { required: true, minLength: 3, maxLength: 80 })}
        <div className="space-y-1 sm:col-span-2">
          <label htmlFor="c-body" className="text-xs text-muted-foreground">
            Description (optional)
          </label>
          <Textarea id="c-body" maxLength={200} value={form.body ?? ''} onChange={(e) => set('body', e.target.value)} />
        </div>
        {field('target_url', 'Destination (https only)', { required: true, type: 'url', pattern: 'https://.*' })}
        {field('cta_label', 'Button label', { required: true, minLength: 2, maxLength: 24 })}
        {field('image_url', 'Logo URL (https, optional)', { type: 'url', pattern: 'https://.*' })}
        <div className="space-y-1">
          <label htmlFor="c-weight" className="text-xs text-muted-foreground">
            Weight (rotation share)
          </label>
          <Input id="c-weight" type="number" min={1} max={100} value={form.weight ?? 1} onChange={(e) => set('weight', Number(e.target.value) || 1)} />
        </div>
      </div>

      <fieldset className="space-y-1">
        <legend className="text-xs text-muted-foreground">Placements</legend>
        <div className="flex flex-wrap gap-4">
          {placements.map((p) => (
            <label key={p.key} className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={form.placements.includes(p.key)}
                onChange={(e) => set('placements', e.target.checked ? [...form.placements, p.key] : form.placements.filter((k: Placement) => k !== p.key))}
              />
              {p.label}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-4">
        <div className="space-y-1">
          <label htmlFor="c-model" className="text-xs text-muted-foreground">
            Pricing
          </label>
          <select id="c-model" className={SELECT} value={form.pricing_model} onChange={(e) => set('pricing_model', e.target.value as SponsorPricingModel)}>
            {(['cpm', 'cpc', 'flat'] as const).map((m) => (
              <option key={m} value={m}>
                {m.toUpperCase()}: {pricingLabel(m)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="c-rate" className="text-xs text-muted-foreground">
            Rate ({currency})
          </label>
          <Input id="c-rate" type="number" min={0} step="any" required value={form.rate} onChange={(e) => set('rate', e.target.value)} />
        </div>
        <div className="space-y-1">
          <label htmlFor="c-budget" className="text-xs text-muted-foreground">
            Budget ({currency}, optional)
          </label>
          <Input id="c-budget" type="number" min={0} step="any" value={form.budget ?? ''} onChange={(e) => set('budget', e.target.value)} />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <div className="space-y-1">
          <label htmlFor="c-start" className="text-xs text-muted-foreground">
            Starts (UTC, optional)
          </label>
          <Input id="c-start" type="datetime-local" value={form.starts_at ?? ''} onChange={(e) => set('starts_at', e.target.value)} />
        </div>
        <div className="space-y-1">
          <label htmlFor="c-end" className="text-xs text-muted-foreground">
            Ends (UTC, optional)
          </label>
          <Input id="c-end" type="datetime-local" value={form.ends_at ?? ''} onChange={(e) => set('ends_at', e.target.value)} />
        </div>
      </div>

      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={save.isPending || form.placements.length === 0}>
          {editing ? 'Save changes' : 'Create draft'}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export default function OperatorSponsorshipsPage() {
  const settings = useAdSettings();
  const campaigns = useCampaigns();
  const config = usePaymentsConfig();
  const status = useSetCampaignStatus();
  const [editing, setEditing] = useState<Campaign | 'new' | null>(null);
  const currency = config.data?.currency ?? 'NGN';

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sponsorships"
        description="Optional sponsored placements for relevant AI tools, GPU hardware and infrastructure providers. Compute commission is the primary revenue; sponsorship revenue is reported separately on the Revenue page."
      />

      {settings.error ? <ErrorState message={errorMessage(settings.error)} /> : settings.data ? <SettingsCard key={settings.data.updated_at} settings={settings.data} /> : <TableSkeleton />}

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1.5">
            <CardTitle>Campaigns</CardTitle>
            <CardDescription>New campaigns start as drafts. Impressions count once per view when at least half the item is visible; clicks count once per view.</CardDescription>
          </div>
          {editing === null && (
            <Button size="sm" onClick={() => setEditing('new')} disabled={!settings.data}>
              New campaign
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {editing !== null && settings.data && (
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <CampaignForm
                key={editing === 'new' ? 'new' : editing.id}
                editing={editing === 'new' ? null : editing}
                placements={settings.data.placements}
                currency={currency}
                onDone={() => setEditing(null)}
              />
            </div>
          )}
          {campaigns.error ? (
            <ErrorState message={errorMessage(campaigns.error)} />
          ) : campaigns.isLoading ? (
            <TableSkeleton />
          ) : (campaigns.data ?? []).length === 0 ? (
            <EmptyState>No campaigns yet.</EmptyState>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Campaign</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Impressions</TableHead>
                  <TableHead className="text-right">Clicks</TableHead>
                  <TableHead className="text-right">CTR</TableHead>
                  <TableHead className="text-right">Last 30 days</TableHead>
                  <TableHead className="text-right">Earned</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(campaigns.data ?? []).map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <div className="text-sm font-medium">{c.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {c.sponsor} · {CATEGORY_LABEL[c.category]} · {c.pricing_model.toUpperCase()} {money(c.rate, currency)}
                        {c.budget ? ` · budget ${money(c.budget, currency)}` : ''}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      <span className="capitalize">{c.status}</span>
                      {c.status === 'active' && !c.serving && <div className="text-xs text-muted-foreground">not serving (schedule or budget)</div>}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.impressions.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.clicks.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.ctr === null ? '—' : `${(c.ctr * 100).toFixed(2)}%`}</TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {c.last_30_days.impressions.toLocaleString()} / {c.last_30_days.clicks.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">{money(c.earned, currency)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {c.status !== 'ended' && (
                          <Button size="sm" variant="ghost" onClick={() => setEditing(c)}>
                            Edit
                          </Button>
                        )}
                        {NEXT[c.status].map((n) => (
                          <Button
                            key={n.to}
                            size="sm"
                            variant={n.to === 'ended' ? 'destructive' : 'outline'}
                            disabled={status.isPending}
                            onClick={() => {
                              if (n.to === 'ended' && !window.confirm(`End "${c.name}"? Ended campaigns cannot be restarted.`)) return;
                              status.mutate({ id: c.id, status: n.to }, { onError: (err) => toast.error(errorMessage(err)) });
                            }}
                          >
                            {n.label}
                          </Button>
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
