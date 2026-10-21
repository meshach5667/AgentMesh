import Link from 'next/link';
import { ArrowRight, Check } from 'lucide-react';
import { CodeWindow } from './CodeWindow';

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pb-20 pt-36 md:pt-44">
      <div className="bg-grid mask-radial pointer-events-none absolute inset-0 opacity-60" />
      <div className="pointer-events-none absolute left-1/2 top-0 h-[480px] w-[900px] -translate-x-1/2 rounded-full bg-brand/15 blur-[120px]" />
      <div className="relative mx-auto max-w-6xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <Link
            href="#status"
            className="mb-7 inline-flex items-center gap-2 rounded-full border border-border bg-background/60 py-1 pl-1 pr-3 text-xs text-muted-foreground shadow-soft backdrop-blur transition-colors hover:text-foreground"
          >
            <span className="rounded-full bg-brand px-2 py-0.5 text-[11px] font-medium text-brand-foreground">Open beta</span>
            Payments run in Paystack test mode
            <ArrowRight className="size-3" />
          </Link>
          <h1 className="text-gradient text-5xl font-semibold leading-[1.05] tracking-tighter md:text-7xl">
            Open-weight models,
            <br />
            on the world&apos;s idle compute.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            Deploy Qwen, Llama, SmolLM and other open models in a few clicks. AgentMesh places them on machines contributed
            by independent providers and gives you an OpenAI-compatible endpoint. You pay only while it&apos;s serving.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/register"
              className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-medium text-primary-foreground shadow-lifted transition-transform hover:-translate-y-px"
            >
              Deploy a model <ArrowRight className="size-4" />
            </Link>
            <Link
              href="/register?role=provider"
              className="inline-flex h-11 items-center rounded-xl border border-border bg-background/70 px-5 text-sm font-medium shadow-soft backdrop-blur transition-colors hover:bg-accent"
            >
              Earn with your hardware
            </Link>
          </div>
          <ul className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[13px] text-muted-foreground">
            {['OpenAI-compatible API', 'Ollama & llama.cpp runtimes', 'Billed per ready minute'].map((t) => (
              <li key={t} className="flex items-center gap-1.5">
                <Check className="size-3.5 text-brand" /> {t}
              </li>
            ))}
          </ul>
        </div>
        <div className="relative mx-auto mt-16 max-w-4xl">
          <CodeWindow />
        </div>
      </div>
    </section>
  );
}
