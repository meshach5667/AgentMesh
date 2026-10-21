import Link from 'next/link';
import { ArrowDown, ArrowRight, Check, Cpu, Globe2, Layers3, Network, Sparkles } from 'lucide-react';
import { CodeWindow } from './CodeWindow';

export function HeroSection() {
  return (
    <section className="relative isolate overflow-hidden pb-20 pt-32 md:pb-24 md:pt-40">
      <div className="bg-grid mask-radial pointer-events-none absolute inset-0 opacity-45" />
      <div className="pointer-events-none absolute -right-40 top-10 size-[620px] rounded-full bg-brand/10 blur-[130px]" />
      <div className="pointer-events-none absolute -left-56 top-64 size-[500px] rounded-full bg-cyan-500/[0.08] blur-[130px]" />
      <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-6 lg:grid-cols-[1.02fr_0.98fr] lg:gap-10">
        <div className="max-w-2xl">
          <Link
            href="#status"
            className="mb-7 inline-flex items-center gap-2 rounded-full border border-brand/20 bg-brand/[0.06] py-1 pl-1 pr-3 text-xs font-medium text-foreground/80 shadow-soft backdrop-blur transition-colors hover:bg-brand/10"
          >
            <span className="flex size-6 items-center justify-center rounded-full bg-brand text-brand-foreground"><Sparkles className="size-3" /></span>
            Open beta <span className="text-muted-foreground">·</span> Community compute
            <ArrowRight className="size-3" />
          </Link>
          <h1 className="text-gradient text-5xl font-semibold leading-[1.02] tracking-[-0.055em] sm:text-6xl md:text-7xl">
            AI compute,
            <br />
            <span className="text-brand-gradient">without the cloud overhead.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground md:text-[19px]">
            Run open-weight models on a distributed network of independent machines. Deploy in minutes, call through the API you already use, and pay as you serve.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/register"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-brand px-5 text-sm font-semibold text-brand-foreground shadow-[0_10px_30px_-12px_color-mix(in_oklch,var(--brand)_75%,transparent)] transition-all hover:-translate-y-0.5 hover:brightness-110"
            >
              Start building <ArrowRight className="size-4" />
            </Link>
            <Link
              href="/register?role=provider"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-border/80 bg-card/70 px-5 text-sm font-medium shadow-soft backdrop-blur transition-colors hover:border-brand/35 hover:bg-card"
            >
              Add your compute <ArrowDown className="size-4 -rotate-45" />
            </Link>
          </div>
          <ul className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-[12px] text-muted-foreground">
            {['OpenAI-compatible API', 'Open model runtimes', 'Usage-based billing'].map((t) => (
              <li key={t} className="flex items-center gap-1.5">
                <Check className="size-3.5 text-brand" /> {t}
              </li>
            ))}
          </ul>
        </div>
        <div className="relative mx-auto w-full max-w-2xl lg:ml-auto">
          <div className="pointer-events-none absolute -inset-5 rounded-[2rem] bg-gradient-to-br from-brand/15 via-transparent to-cyan-500/10 blur-2xl" />
          <div className="relative rounded-[1.6rem] border border-border/80 bg-card/80 p-3 shadow-lifted backdrop-blur-xl sm:p-4">
            <div className="flex items-center justify-between px-2 pb-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand">The AgentMesh network</p>
                <p className="mt-1 text-sm font-medium">One API. A distributed fabric.</p>
              </div>
              <span className="rounded-full border border-border bg-background/70 px-2.5 py-1 text-[10px] font-medium text-muted-foreground">Concept</span>
            </div>
            <div className="relative overflow-hidden rounded-2xl border border-border/80 bg-background/80 px-5 py-7 sm:px-7">
              <div className="bg-grid pointer-events-none absolute inset-0 opacity-30" />
              <div className="relative grid grid-cols-[1fr_46px_1fr] items-center gap-y-6 sm:grid-cols-[1fr_72px_1fr]">
                <div className="rounded-xl border border-brand/20 bg-brand/[0.07] p-3 sm:p-4">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-brand text-brand-foreground"><Layers3 className="size-4" /></div>
                  <p className="mt-3 text-xs font-semibold sm:text-sm">Your application</p>
                  <p className="mt-1 text-[10px] text-muted-foreground sm:text-xs">Existing API client</p>
                </div>
                <div className="relative flex h-full items-center justify-center">
                  <span className="absolute left-0 right-0 border-t border-dashed border-brand/50" />
                  <span className="relative z-10 rounded-full border border-brand/25 bg-background px-1.5 py-1 text-[9px] font-mono text-brand sm:px-2.5 sm:text-[10px]">API</span>
                </div>
                <div className="rounded-xl border border-border bg-card p-3 shadow-soft sm:p-4">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-foreground text-background"><Cpu className="size-4" /></div>
                  <p className="mt-3 text-xs font-semibold sm:text-sm">Open models</p>
                  <p className="mt-1 text-[10px] text-muted-foreground sm:text-xs">Verified runtimes</p>
                </div>
                <div className="col-span-3 flex justify-center py-1">
                  <div className="flex items-center gap-2 rounded-full border border-border bg-card/90 px-3 py-1.5 text-[10px] font-medium text-muted-foreground shadow-soft sm:text-xs">
                    <Globe2 className="size-3.5 text-brand" /> Independent community compute
                  </div>
                </div>
                <div className="col-span-3 grid grid-cols-3 gap-2 sm:gap-3">
                  {['Independent nodes', 'Capacity matching', 'Health-aware routing'].map((label, i) => (
                    <div key={label} className="flex min-h-14 flex-col items-center justify-center gap-1 rounded-xl border border-border/80 bg-card/80 px-1 py-2 text-center sm:min-h-16">
                      <span className="flex size-5 items-center justify-center rounded-md bg-brand/10 text-[9px] font-semibold text-brand">{i + 1}</span>
                      <span className="text-[9px] font-medium text-muted-foreground sm:text-[10px]">{label}</span>
                    </div>
                  ))}
                </div>
                <div className="col-span-3 flex items-center justify-center gap-2 pt-1 text-[10px] text-muted-foreground">
                  <Network className="size-3.5 text-brand" /> Compute contributed by independent providers
                </div>
              </div>
            </div>
            <div className="pt-3 sm:pt-4">
              <CodeWindow />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
