const STEPS = [
  ['Detect', 'Every machine heartbeats about every 15 seconds. A late heartbeat stops new work going there; a node silent for 90 seconds is marked offline.'],
  ['Release', 'Its deployments are released and their attempt is closed. A model that fails by itself is not retried elsewhere, because another node would fail the same way.'],
  ['Choose', 'The scheduler picks the cheapest healthy machine with the same requirements, within your price limits and provider choice, never one that already failed it.'],
  ['Restart', 'The model is started on the replacement from its pinned source and verified with a test generation. If no machine fits, it waits and retries with backoff.'],
];

/** How failover works, stated as precisely as the implementation behaves. */
export function Failover() {
  return (
    <section id="failover" className="py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-2xl">
          <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Reliability</p>
          <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight md:text-[2.75rem] md:leading-[1.1]">
            When a node fails, your deployment moves.
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Machines on a community network come and go. AgentMesh watches them and restarts affected deployments on
            another suitable machine automatically. It is a restart, not a live migration: requests in flight on the
            failed node are lost and can be retried.
          </p>
        </div>
        <ol className="mt-14 grid gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-4">
          {STEPS.map(([title, body], i) => (
            <li key={title} className="bg-background p-7">
              <span className="font-mono text-xs text-muted-foreground">0{i + 1}</span>
              <h3 className="mt-3 text-[15px] font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </li>
          ))}
        </ol>
        <figure className="mt-10 overflow-x-auto rounded-xl border border-border bg-card p-6">
          <svg viewBox="0 0 720 150" role="img" aria-labelledby="failover-title" className="mx-auto h-auto w-full max-w-3xl">
            <title id="failover-title">
              A deployment on node A, which stops heartbeating; the control plane restarts it on node B; the old node is
              told to stop if it comes back.
            </title>
            <g className="fill-none stroke-border" strokeWidth="1.5">
              <rect x="10" y="45" width="160" height="60" rx="10" />
              <rect x="280" y="45" width="160" height="60" rx="10" />
              <rect x="550" y="45" width="160" height="60" rx="10" />
            </g>
            <g className="fill-current text-foreground" fontSize="13" textAnchor="middle">
              <text x="90" y="72">Node A</text>
              <text x="360" y="72">Control plane</text>
              <text x="630" y="72">Node B</text>
            </g>
            <g className="fill-current text-muted-foreground" fontSize="11" textAnchor="middle">
              <text x="90" y="90">heartbeats stop</text>
              <text x="360" y="90">picks a healthy match</text>
              <text x="630" y="90">attempt 2 serves</text>
              <text x="225" y="35">offline after 90 s</text>
              <text x="495" y="35">deploy (signed)</text>
              <text x="225" y="128">stale reports refused</text>
            </g>
            <g className="stroke-muted-foreground" strokeWidth="1.5" fill="none">
              <path d="M170 60 H272" strokeDasharray="4 4" />
              <path d="M440 60 H542" />
              <path d="M280 95 H178" strokeDasharray="2 4" />
            </g>
          </svg>
        </figure>
      </div>
    </section>
  );
}
