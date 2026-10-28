'use client';

import { AccountCard } from '@/components/account/AccountCard';
import Link from 'next/link';
import { PageHeader } from '@/components/common/Notices';

export default function ProviderSettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Settings" />
      <AccountCard />
      <p className="text-sm text-muted-foreground">
        Your public profile, payment arrangement and default machine prices are on{' '}
        <Link href="/provider/payments" className="underline underline-offset-4">
          Profile &amp; payment
        </Link>
        . Node credentials are per machine: create an enrollment token under Add a Machine, and revoke a machine from its
        node page.
      </p>
    </div>
  );
}
