import { AuthGuard } from '../../components/auth/AuthGuard';
import { DashboardLayout } from '../../components/layout/DashboardLayout';

export default function ProviderLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <DashboardLayout>
        {children}
      </DashboardLayout>
    </AuthGuard>
  );
}
