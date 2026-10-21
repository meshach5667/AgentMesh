import Link from 'next/link';
import { ArrowUpRight, Check, Cpu, Network, Sparkles } from 'lucide-react';
import { Logo } from '@/components/brand/Logo';
import { cn } from '@/lib/utils';

const POINTS = [
  'OpenAI-compatible endpoints for open-weight models',
  'Placement, health checks and failover handled for you',
  'Prepaid, itemised billing with provider payouts',
];

/** Open, editorial split layout for sign-in and sign-up. */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-background">
      <div className="pointer-events-none absolute -left-48 top-20 size-[520px] rounded-full bg-brand/[0.08] blur-[130px]" />
      <div className="relative grid min-h-screen lg:grid-cols-[1.04fr_0.96fr]">
        <section className="flex min-h-screen flex-col px-6 py-7 sm:px-10 lg:px-16 lg:py-9">
          <div className="flex items-center justify-between">
            <Logo />
            <Link href="/" className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground">
              Back to home
            </Link>
          </div>
          <div className="flex flex-1 items-center justify-center py-12 lg:py-16">
            <div className="w-full max-w-[420px]">{children}</div>
          </div>
          <div className="flex items-center justify-between gap-4 text-xs text-muted-foreground">
            <Link href="/#trust" className="transition-colors hover:text-foreground">
              How AgentMesh handles your data
            </Link>
            <span>© {new Date().getFullYear()} AgentMesh</span>
          </div>
        </section>

        <aside className="relative hidden min-h-screen overflow-hidden bg-[#111426] text-white lg:flex lg:flex-col lg:justify-between lg:px-12 lg:py-10 xl:px-16">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_78%_16%,rgba(100,86,255,0.28),transparent_42%),radial-gradient(ellipse_at_10%_90%,rgba(21,187,190,0.12),transparent_40%)]" />
          <div className="bg-grid pointer-events-none absolute inset-0 opacity-[0.12]" />
          <div className="relative flex items-center gap-2 text-sm font-medium text-white/70">
            <span className="flex size-7 items-center justify-center rounded-full bg-white/10 text-violet-200"><Sparkles className="size-3.5" /></span>
            A new kind of model infrastructure
          </div>

          <div className="relative py-14">
            <div className="mb-10 flex items-center justify-center">
              <div className="relative flex size-64 items-center justify-center">
                <div className="absolute inset-4 rounded-full border border-white/10" />
                <div className="absolute inset-10 rounded-full border border-dashed border-violet-300/25" />
                <div className="absolute inset-[4.5rem] rounded-full border border-white/10" />
                <div className="absolute left-8 top-[4.5rem] h-px w-40 rotate-[26deg] bg-gradient-to-r from-cyan-300/0 via-cyan-200/50 to-violet-300/0" />
                <div className="absolute bottom-14 left-12 h-px w-40 -rotate-[28deg] bg-gradient-to-r from-violet-300/0 via-violet-200/50 to-cyan-300/0" />
                <div className="absolute left-1/2 top-8 h-40 w-px -rotate-[18deg] bg-gradient-to-b from-violet-300/0 via-violet-200/40 to-cyan-300/0" />
                <div className="relative z-10 flex size-[4.5rem] items-center justify-center rounded-full border border-white/15 bg-white/[0.08] shadow-[0_0_60px_rgba(130,115,255,0.25)] backdrop-blur-xl">
                  <Network className="size-7 text-violet-100" />
                </div>
                <span className="absolute left-4 top-16 flex size-10 items-center justify-center rounded-full border border-white/10 bg-[#1c2038] text-cyan-200"><Cpu className="size-4" /></span>
                <span className="absolute right-8 top-12 flex size-9 items-center justify-center rounded-full border border-white/10 bg-[#1c2038] text-violet-200"><Cpu className="size-3.5" /></span>
                <span className="absolute bottom-9 left-16 flex size-8 items-center justify-center rounded-full border border-white/10 bg-[#1c2038] text-cyan-100"><Cpu className="size-3" /></span>
                <span className="absolute bottom-14 right-5 flex size-11 items-center justify-center rounded-full border border-white/10 bg-[#1c2038] text-violet-200"><Cpu className="size-4" /></span>
              </div>
            </div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-200/80">The AgentMesh network</p>
            <h2 className="mt-4 max-w-xl text-4xl font-semibold leading-[1.08] tracking-[-0.045em] xl:text-5xl">
              Open models.
              <br />
              Shared compute.
              <br />
              <span className="text-white/55">One simple API.</span>
            </h2>
            <ul className="mt-8 space-y-3">
              {POINTS.map((point) => (
                <li key={point} className="flex items-center gap-3 text-sm text-white/65">
                  <Check className="size-4 shrink-0 text-cyan-200" />
                  {point}
                </li>
              ))}
            </ul>
          </div>

          <div className="relative flex items-center justify-between border-t border-white/10 pt-5 text-xs text-white/45">
            <span>Compute from independent providers</span>
            <Link href="/#how-it-works" className="inline-flex items-center gap-1.5 transition-colors hover:text-white/80">
              Explore the network <ArrowUpRight className="size-3.5" />
            </Link>
          </div>
        </aside>
      </div>
    </main>
  );
}

export function Field({ label, children, aside }: { label: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="flex items-center justify-between text-[13px] font-medium text-foreground/85">
        {label}
        {aside}
      </span>
      {children}
    </label>
  );
}

export const inputClass = cn(
  'h-12 w-full rounded-xl border border-transparent bg-muted/75 px-4 text-sm shadow-none outline-none transition-all',
  'placeholder:text-muted-foreground/60 hover:bg-muted focus:border-brand/35 focus:bg-card focus:ring-4 focus:ring-brand/10',
);

export const submitClass =
  'group inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-brand px-5 text-sm font-semibold text-brand-foreground shadow-[0_12px_28px_-16px_color-mix(in_oklch,var(--brand)_85%,transparent)] transition-all hover:-translate-y-0.5 hover:brightness-110 disabled:translate-y-0 disabled:opacity-60';
