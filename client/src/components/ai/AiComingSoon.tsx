import Link from 'next/link';
import { Sparkles } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { PageHeader } from '@/components/common/Notices';

const PLANNED = [
  'Describe the deployment you want in plain language.',
  'An AI agent picks a model from the approved catalog and plans the deployment.',
  'AgentMesh enforces your budget and limits, verifies the result, and stops it when a limit is reached.',
];

/** Shown in place of AI Deploy until the AI inference machine is configured (NEXT_PUBLIC_AI_DEPLOY_ENABLED). */
export function AiComingSoon() {
  return (
    <div className="space-y-6">
      <PageHeader title="AI Deploy" description="Plain-language, AI-assisted model deployment." />
      <Card>
        <CardContent className="flex flex-col items-center gap-5 py-14 text-center">
          <span className="flex size-12 items-center justify-center rounded-full border border-border bg-muted">
            <Sparkles className="size-5" />
          </span>
          <div>
            <span className="rounded-full border border-border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">Coming soon</span>
            <h2 className="mt-4 text-xl font-semibold tracking-tight">AI-assisted deployment is on its way</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
              This feature is not available yet. Nothing here runs or charges your wallet.
            </p>
          </div>
          <ol className="max-w-md space-y-2 text-left text-sm text-muted-foreground">
            {PLANNED.map((step, i) => (
              <li key={step} className="flex gap-3">
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-border font-mono text-[11px]">{i + 1}</span>
                {step}
              </li>
            ))}
          </ol>
          <Link href="/customer/models" className="inline-flex h-9 items-center rounded-lg bg-foreground px-4 text-[13px] font-medium text-background transition-opacity hover:opacity-85">
            Deploy from the catalog
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
