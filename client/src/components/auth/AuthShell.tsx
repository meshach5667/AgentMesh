import Link from 'next/link';
import { Check } from 'lucide-react';
import { Logo } from '@/components/brand/Logo';
import { cn } from '@/lib/utils';

const POINTS = [
  'OpenAI-compatible endpoints for open-weight models',
  'Placement, health checks and failover handled for you',
  'Prepaid, itemised billing; providers paid via Paystack',
];

/** Split layout for sign-in and sign-up: form on the left, product panel on the right. */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Logo />
        <div className="flex flex-1 items-center justify-center py-12">
          <div className="w-full max-w-sm">{children}</div>
        </div>
        <p className="text-xs text-muted-foreground">
          <Link href="/#trust" className="underline-offset-4 hover:underline">
            How AgentMesh handles your data
          </Link>
        </p>
      </div>
      <div className="relative hidden overflow-hidden border-l border-border bg-muted/40 lg:block">
        <div className="bg-grid mask-radial absolute inset-0 opacity-70" />
        <div className="absolute -right-24 top-1/4 size-[420px] rounded-full bg-brand/20 blur-[110px]" />
        <div className="relative flex h-full flex-col justify-center px-16">
          <h2 className="text-gradient max-w-md text-4xl font-semibold leading-tight tracking-tight">
            Open-weight models on the world&apos;s idle compute.
          </h2>
          <ul className="mt-8 space-y-4">
            {POINTS.map((p) => (
              <li key={p} className="flex items-start gap-3 text-sm text-muted-foreground">
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-soft">
                  <Check className="size-3 text-brand" />
                </span>
                {p}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export function Field({ label, children, aside }: { label: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="flex items-center justify-between text-[13px] font-medium">
        {label}
        {aside}
      </span>
      {children}
    </label>
  );
}

export const inputClass = cn(
  'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm shadow-soft outline-none transition-shadow',
  'placeholder:text-muted-foreground/70 focus:border-brand/50 focus:ring-4 focus:ring-brand/15',
);

export const submitClass =
  'inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary text-sm font-medium text-primary-foreground shadow-soft transition-opacity hover:opacity-90 disabled:opacity-60';
