import { Check, ShieldAlert } from 'lucide-react';

const WORKING = [
  'Deploy approved open-weight models (Ollama, llama.cpp) and call them through an OpenAI-compatible API, with streaming',
  'Health monitoring from heartbeats, with late, offline, recovering and repeatedly failing nodes kept out of scheduling',
  'API keys, per-key deployment scoping, and per-request usage metering (no prompt or response content stored)',
  'A Docker worker and an installable agent for Linux and macOS with resource limits, pause, drain and availability schedules',
  'Provider, customer and operator dashboards backed by live data, with an audit log',
  'Providers price each machine in their own currency and publish how they are paid; customers pay them directly, with itemised cost estimates',
  'Deployments go to the cheapest healthy machine within your price limits; when a node fails they restart on another suitable one',
];

export function Status() {
  return (
    <section className="border-t border-border bg-muted/30 py-28" id="status">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-2xl">
          <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Status</p>
          <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight md:text-[2.75rem] md:leading-[1.1]">What works today</h2>
          <p className="mt-4 text-lg text-muted-foreground">AgentMesh is early. Here is the honest state of the product.</p>
        </div>
        <div className="mt-14 rounded-xl border border-border bg-card p-7">
          <h3 className="text-sm font-semibold">Working</h3>
          <ul className="mt-5 grid gap-x-10 gap-y-3.5 text-sm md:grid-cols-2">
            {WORKING.map((t) => (
              <li key={t} className="flex gap-3">
                <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/15">
                  <Check className="size-2.5 text-emerald-600 dark:text-emerald-400" />
                </span>
                <span className="leading-relaxed">{t}</span>
              </li>
            ))}
          </ul>
        </div>
        <div id="trust" className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/[0.06] p-7">
          <div className="flex items-start gap-4">
            <ShieldAlert className="mt-0.5 size-5 shrink-0 text-amber-500" />
            <div>
              <h3 className="font-semibold">Trust model</h3>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
                Models run on computers owned by independent providers. A provider can inspect the model files, the
                process memory, and every prompt and response its node handles. Container isolation protects the
                provider&apos;s machine; it does not hide your data from the provider. Don&apos;t send confidential data to
                community nodes.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
