'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { CodeBlock, InlineValue } from '@/components/common/CodeBlock';
import { Notice, PageHeader } from '@/components/common/Notices';
import { useCreateEnrollmentToken } from '@/hooks/useNodes';
import { CONTROL_PLANE_URL } from '@/lib/config';
import { errorMessage } from '@/lib/errors';
import { dateTime } from '@/lib/format';

export default function EnrollNodePage() {
  const create = useCreateEnrollmentToken();
  const [name, setName] = useState('');
  const [region, setRegion] = useState('');
  const [mode, setMode] = useState<'agent' | 'docker'>('agent');
  const token = create.data?.token;

  const agentCmd = [
    'cd AgentMesh/server',
    'python scripts/build_worker_wheel.py   # or use a wheel published by your operator',
    `./packaging/install.sh --control-plane ${CONTROL_PLANE_URL} --token ${token ?? '<token>'} \\`,
    '    --max-ram-mb 8192 --max-cpu 4 --max-disk-mb 30000',
  ].join('\n');
  const dockerCmd = [
    `export AGENTMESH_CONTROL_PLANE_URL=${CONTROL_PLANE_URL}`,
    `export AGENTMESH_ENROLLMENT_TOKEN=${token ?? '<token>'}`,
    'export DOCKER_GID=$(getent group docker | cut -d: -f3)',
    'export AGENTMESH_MAX_RAM_MB=8192 AGENTMESH_MAX_CPU_CORES=4 AGENTMESH_MAX_DISK_MB=30000',
    'docker compose -f docker-compose.worker.yml up -d',
  ].join('\n');

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Add a machine" description="Enroll a computer as an AgentMesh node. The worker only makes outbound connections; you do not need to open any ports." />

      <Card>
        <CardHeader>
          <CardTitle>1. Create a one-time enrollment token</CardTitle>
          <CardDescription>The token works once and expires after 60 minutes. Create a new one for each machine.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate({ name: name.trim() || undefined, region: region.trim() || undefined });
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="node-name">Name (optional)</Label>
              <Input id="node-name" maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder="office-desktop" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="node-region">Region (optional)</Label>
              <Input id="node-region" maxLength={100} value={region} onChange={(e) => setRegion(e.target.value)} placeholder="eu-west" />
            </div>
            <Button type="submit" disabled={create.isPending}>
              {token ? 'Create another' : 'Create token'}
            </Button>
          </form>
          {create.error && <p className="mt-3 text-sm text-rose-500">{errorMessage(create.error)}</p>}
          {create.data && (
            <div className="mt-4 space-y-2">
              <InlineValue value={create.data.token} />
              <p className="text-xs text-muted-foreground">Expires {dateTime(create.data.expires_at)}. It is shown only now.</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Install the worker</CardTitle>
          <CardDescription>
            The limits you pass are the most AgentMesh will ever reserve on the machine. Full instructions are in
            docs/WORKER.md.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div role="tablist" className="flex gap-1">
            {(['agent', 'docker'] as const).map((m) => (
              <button
                key={m}
                role="tab"
                type="button"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
                className={`rounded-md px-3 py-1 text-sm ${mode === m ? 'bg-muted font-medium' : 'text-muted-foreground'}`}
              >
                {m === 'agent' ? 'Installable agent (Linux, macOS)' : 'Docker worker'}
              </button>
            ))}
          </div>
          {mode === 'agent' ? (
            <>
              <p className="text-sm text-muted-foreground">
                Needs Python 3.11+ and Ollama (for the Ollama runtime). No admin rights. Runs as a per-user service and
                starts its own isolated model servers; it never touches your own Ollama service or models.
              </p>
              <CodeBlock code={agentCmd} />
            </>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">Needs Docker Engine 24+. Run from the repository root.</p>
              <CodeBlock code={dockerCmd} />
              <Notice tone="warning">
                The worker uses the Docker socket, which is equivalent to root access on the machine. Prefer rootless
                Docker and a machine dedicated to this purpose.
              </Notice>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Check it appears</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            The machine shows up in{' '}
            <Link href="/provider/nodes" className="underline underline-offset-4">
              My nodes
            </Link>{' '}
            within a few seconds of enrolling. If it does not, run <code className="font-mono">agentmesh-worker doctor</code>{' '}
            on the machine.
          </p>
        </CardContent>
      </Card>

      <Notice tone="info" title="What hosting means for you">
        AgentMesh runs open-weight models on your machine inside resource limits. You can pause, drain or remove the
        worker at any time. Requests and responses pass through your machine; do not use it to inspect customers&apos;
        data. You earn a share of what customers pay while your node serves their deployments, and withdraw it to a bank account from Earnings &amp; Payouts.
      </Notice>
    </div>
  );
}
