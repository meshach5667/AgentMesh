import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { count, dateTime, money, shortId } from '@/lib/format';
import type { CostEstimate } from '@/types';

/** Cost estimates per window of use: READY time and tokens at the machine's published prices. Not payments. */
export function EstimatesTable({
  estimates,
  empty,
  showCustomer = false,
  showDeployment = false,
}: {
  estimates: CostEstimate[];
  empty: string;
  showCustomer?: boolean;
  showDeployment?: boolean;
}) {
  if (estimates.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Period</TableHead>
            {showDeployment && <TableHead>Deployment</TableHead>}
            {showCustomer && <TableHead>Customer ref</TableHead>}
            <TableHead className="text-right">Ready time</TableHead>
            <TableHead className="text-right">Tokens in / out</TableHead>
            <TableHead className="text-right">Estimated amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {estimates.map((e) => (
            <TableRow key={e.id}>
              <TableCell className="text-xs">
                {dateTime(e.period_start)} – {dateTime(e.period_end)}
              </TableCell>
              {showDeployment && <TableCell className="font-mono text-xs">{shortId(e.deployment_id)}</TableCell>}
              {showCustomer && <TableCell className="font-mono text-xs">{e.customer_ref ?? '—'}</TableCell>}
              <TableCell className="text-right text-xs tabular-nums">{(e.ready_seconds / 3600).toFixed(2)} h</TableCell>
              <TableCell className="text-right text-xs tabular-nums">
                {count(e.input_tokens)} / {count(e.output_tokens)}
              </TableCell>
              <TableCell className="text-right tabular-nums">{money(e.amount, e.currency)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
