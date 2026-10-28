import { Activity, BadgeCheck, Gauge, HandCoins, Plug, ShieldCheck } from 'lucide-react';

const FEATURES = [
  {
    icon: Plug,
    title: 'Drop-in OpenAI API',
    body: 'Every deployment gets a /v1 endpoint with chat, completions and streaming. Point your existing OpenAI client at it and keep your code.',
  },
  {
    icon: Gauge,
    title: 'Cheapest machine that fits',
    body: 'The scheduler picks the cheapest healthy machine with the CPU, memory, GPU and runtime your model needs, within your price limits, and tells you exactly why when none fits.',
  },
  {
    icon: Activity,
    title: 'Automatic failover',
    body: 'When a node stops heartbeating or fails health checks, the deployment is restarted on another suitable node. Same id, same endpoint, same keys, and never a pricier machine without your approval.',
  },
  {
    icon: BadgeCheck,
    title: 'Verified models',
    body: 'Weights are pinned to exact versions and checked by digest. A deployment only goes live after a real test generation passes.',
  },
  {
    icon: HandCoins,
    title: 'Pay providers directly',
    body: 'Providers set their own prices. You buy prepaid credit with them directly, verified by AgentMesh before service starts; no commission, itemised cost estimates.',
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
          <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Product</p>
          <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight md:text-[2.75rem] md:leading-[1.1]">Infrastructure you don&apos;t have to run.</h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Everything between &ldquo;I want this model&rdquo; and a production endpoint: placement, health monitoring,
            failover, keys and usage.
          </p>
        </div>
        <div className="mt-14 grid gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="bg-background p-8 transition-colors hover:bg-muted/40"
            >
              <Icon className="size-5 text-foreground" strokeWidth={1.6} />
              <h3 className="mt-6 text-[15px] font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
