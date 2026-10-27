import type { Metadata } from 'next';
import { AuthShell } from '@/components/auth/AuthShell';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { MfaSetup } from '@/components/auth/MfaSetup';
import { NO_INDEX } from '@/lib/seo';

export const metadata: Metadata = { title: 'Two-factor authentication', robots: NO_INDEX };

export default function MfaSetupPage() {
  return (
    <AuthGuard allowMfaPending>
      <AuthShell>
        <MfaSetup />
      </AuthShell>
    </AuthGuard>
  );
}
