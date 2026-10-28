import { ExternalLink } from 'lucide-react';
import { safeExternalUrl } from '@/lib/billing';
import { money } from '@/lib/format';
import { PAYMENT_METHOD_LABEL, type PaymentProfile } from '@/types';

/**
 * A provider's payment arrangement as customers see it. AgentMesh shows it and processes, verifies or holds nothing:
 * the wording says so wherever it appears.
 */
export function PaymentArrangement({
  payment,
  providerName,
  reference,
}: {
  payment: PaymentProfile | null;
  providerName: string;
  reference?: string;
}) {
  if (!payment || (!payment.methods.length && !payment.instructions && !payment.links.length)) {
    return (
      <p className="text-sm text-muted-foreground">
        {providerName} has not published how to pay them yet. Contact them before relying on a priced machine.
      </p>
    );
  }
  const links = payment.links.map((l) => ({ ...l, safe: safeExternalUrl(l.url) })).filter((l) => l.safe);
  return (
    <div className="space-y-3 text-sm">
      {payment.methods.length > 0 && (
        <p>
          <span className="text-muted-foreground">Accepts: </span>
          {payment.methods.map((m) => PAYMENT_METHOD_LABEL[m] ?? m).join(', ')}
          {payment.accepted_currencies.length > 0 && (
            <span className="text-muted-foreground"> · in {payment.accepted_currencies.join(', ')}</span>
          )}
        </p>
      )}
      {reference && (
        <p>
          <span className="text-muted-foreground">Your payment reference: </span>
          <span className="font-mono font-medium">{reference}</span>
          <span className="block text-xs text-muted-foreground">Quote it when you pay so {providerName} can match your payment.</span>
        </p>
      )}
      {payment.instructions && <p className="whitespace-pre-line rounded-md border border-border bg-muted/40 p-3">{payment.instructions}</p>}
      {links.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {links.map((l) => (
            <li key={l.safe}>
              <a
                href={l.safe!}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 hover:bg-muted"
              >
                {l.label} <ExternalLink aria-hidden className="size-3.5" />
                <span className="sr-only">(opens {new URL(l.safe!).hostname} in a new tab)</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      {payment.minimum_amount && (
        <p>
          <span className="text-muted-foreground">Minimum: </span>
          {money(payment.minimum_amount, payment.minimum_currency ?? undefined)}
          {payment.minimum_note && <span className="text-muted-foreground"> · {payment.minimum_note}</span>}
        </p>
      )}
      {payment.terms && (
        <p className="whitespace-pre-line">
          <span className="text-muted-foreground">Terms: </span>
          {payment.terms}
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        You pay {providerName} directly. AgentMesh does not process, verify, hold or refund payments, and does not
        charge any fee.
      </p>
    </div>
  );
}
