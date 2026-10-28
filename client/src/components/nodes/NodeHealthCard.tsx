'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useNodeEvents } from '@/hooks/useNodes';
import { errorMessage } from '@/lib/errors';
import { dateTime } from '@/lib/format';
import type { Node } from '@/types';

const EVENT_TEXT: Record<string, string> = {
  'node.heartbeat_late': 'Heartbeats arrived late: no new work until they are on time',
  'node.offline': 'Went offline: its work was moved to other nodes',
  'node.reconnected': 'Reconnected: recovering before it gets new work',
  'node.recovered': 'Recovered: accepting new work again',
  'node.degraded': 'Benched after repeated failed placements',
  'node.quarantined': 'Quarantined by an operator',
  'node.released': 'Released from quarantine',
  'node.revoked': 'Revoked',
  'node.price_set': 'Prices published',
};

/** Health evidence for one machine and its recent history, as the scheduler sees it. */
export function NodeHealthCard({ node }: { node: Node }) {
  const events = useNodeEvents(node.id);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Health history</CardTitle>
        <CardDescription>
          A machine gets new work only while its heartbeats are on time, it has finished recovering from any outage,
          and it is not benched after repeated failures. Work on a machine that goes offline is restarted elsewhere.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid grid-cols-[12rem_1fr] gap-y-2 text-sm">
          <dt className="text-muted-foreground">Health</dt>
          <dd>{node.health ?? '—'}</dd>
          <dt className="text-muted-foreground">Gets new work now</dt>
          <dd>{node.schedulable ? 'Yes' : 'No'}</dd>
          <dt className="text-muted-foreground">Failed placements in a row</dt>
          <dd>{node.consecutive_failures}</dd>
          {node.degraded_until && (
            <>
              <dt className="text-muted-foreground">Benched until</dt>
              <dd>{dateTime(node.degraded_until)}</dd>
            </>
          )}
        </dl>
        {events.isLoading && <p className="text-sm text-muted-foreground">Loading history…</p>}
        {events.error && (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(events.error)}
          </p>
        )}
        {events.data && events.data.length === 0 && <p className="text-sm text-muted-foreground">No health events yet.</p>}
        {events.data && events.data.length > 0 && (
          <ol className="divide-y divide-border text-sm">
            {events.data.slice(0, 20).map((e, i) => (
              <li key={`${e.created_at}-${i}`} className="flex flex-wrap justify-between gap-2 py-2">
                <span>{EVENT_TEXT[e.action] ?? e.action}</span>
                <time className="text-xs text-muted-foreground" dateTime={e.created_at}>
                  {dateTime(e.created_at)}
                </time>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
