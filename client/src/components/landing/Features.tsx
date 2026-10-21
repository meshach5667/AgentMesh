import { Activity, BadgeCheck, CreditCard, Gauge, Plug, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';

const FEATURES = [
  {
    icon: Plug,
    title: 'Drop-in OpenAI API',
    body: 'Every deployment gets a /v1 endpoint with chat, completions and streaming. Point your existing OpenAI client at it and keep your code.',
    wide: true,
  },
  {
    icon: Gauge,
    title: 'Automatic placement',
    body: 'The scheduler reserves CPU, memory and GPU on a node that fits, and tells you exactly why when none does.',
  },
  {
    icon: Activity,
    title: 'Self-healing',
    body: 'When a node goes offline or fails health checks, the deployment moves to another one. Same id, same endpoint, same keys.',
  },
  {
    icon: BadgeCheck,
    title: 'Verified models',
    body: 'Weights are pinned to exact versions and checked by digest. A deployment only goes live after a real test generation passes.',
  },
  {
    icon: CreditCard,
    title: 'Prepaid, per ready minute',
    body: 'Top up with Paystack and pay for reserved resources only while your model is serving, plus tokens. Every charge is itemised.',
    wide: true,
  },
  {
    icon: ShieldCheck,
    title: 'Metering without content',
    body: 'Usage is recorded per request with no prompts or responses stored. API keys can be scoped to a single deployment.',
  },
];

export function Features() {
  return (
    <section id="product" className="py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-brand">Product</p>
          <h2 className="mt-3 text-4xl font-semibold tracking-tight md:text-5xl">Infrastructure you don&apos;t have to run.</h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Everything between &ldquo;I want this model&rdquo; and a production endpoint: scheduling, health, failover, keys and
            billing.
          </p>
        </div>
        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body, wide }) => (
            <div
              key={title}
              className={cn(
                'group relative overflow-hidden rounded-2xl border border-border bg-card p-7 shadow-soft transition-colors hover:border-brand/30',
                wide && 'md:col-span-2',
              )}
            >
              <div className="pointer-events-none absolute -right-16 -top-16 size-48 rounded-full bg-brand/10 opacity-0 blur-3xl transition-opacity group-hover:opacity-100" />
              <span className="flex size-10 items-center justify-center rounded-xl border border-border bg-background shadow-soft">
                <Icon className="size-[18px] text-brand" />
              </span>
              <h3 className="mt-5 text-base font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
