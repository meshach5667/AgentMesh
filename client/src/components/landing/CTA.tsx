import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

export function CTA() {
  return (
    <section className="py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="relative overflow-hidden rounded-3xl border border-border bg-foreground px-8 py-16 text-center text-background shadow-lifted md:px-16">
          <div className="pointer-events-none absolute -top-24 left-1/2 h-64 w-[600px] -translate-x-1/2 rounded-full bg-brand/40 blur-[100px]" />
          <h2 className="relative text-4xl font-semibold tracking-tight md:text-5xl">Ship your first model today.</h2>
          <p className="relative mx-auto mt-4 max-w-xl text-lg opacity-70">
            Start with a small model like SmolLM2 or Qwen2.5 and have an OpenAI-compatible endpoint in minutes.
          </p>
          <div className="relative mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/register" className="inline-flex h-11 items-center gap-2 rounded-xl bg-background px-5 text-sm font-medium text-foreground transition-transform hover:-translate-y-px">
              Get started <ArrowRight className="size-4" />
            </Link>
            <Link href="/register?role=provider" className="inline-flex h-11 items-center rounded-xl border border-background/20 px-5 text-sm font-medium transition-colors hover:bg-background/10">
              Become a provider
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
