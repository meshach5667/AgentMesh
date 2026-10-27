import type { Metadata } from 'next';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { NO_INDEX } from '@/lib/seo';

export const metadata: Metadata = { robots: NO_INDEX };

export default function OperatorLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard roles={['operator', 'admin']}>
      <DashboardLayout>{children}</DashboardLayout>
    </AuthGuard>
  );
}
