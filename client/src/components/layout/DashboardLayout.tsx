import React from 'react';
import { Sidebar, TopBar } from './Sidebar';

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-background font-sans text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="relative flex-1 overflow-y-auto bg-[radial-gradient(ellipse_at_50%_-20%,color-mix(in_oklch,var(--brand)_7%,transparent),transparent_56%)]">
          <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8 sm:py-10">{children}</div>
        </main>
      </div>
    </div>
  );
}
