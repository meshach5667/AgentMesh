'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity, Banknote, BarChart3, Box, CreditCard, KeyRound, LayoutDashboard, LogOut, PlusCircle, Receipt, Scale,
  ScrollText, Server, Settings, Tag, Wallet, type LucideIcon,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useAuth } from '../../hooks/useAuth';
import { Logo } from '@/components/brand/Logo';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

export interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
}
type Section = { title?: string; links: NavLink[] };

export const customerSections: Section[] = [
  {
    links: [
      { href: '/customer', label: 'Overview', icon: LayoutDashboard },
      { href: '/customer/models', label: 'Models', icon: Box },
      { href: '/customer/deployments', label: 'Deployments', icon: Activity },
      { href: '/customer/api-keys', label: 'API Keys', icon: KeyRound },
    ],
  },
  {
    title: 'Billing',
    links: [
      { href: '/customer/usage', label: 'Usage', icon: BarChart3 },
      { href: '/customer/wallet', label: 'Wallet', icon: CreditCard },
      { href: '/customer/transactions', label: 'Transactions', icon: Receipt },
    ],
  },
  { title: 'Account', links: [{ href: '/customer/settings', label: 'Settings', icon: Settings }] },
];

export const providerSections: Section[] = [
  {
    links: [
      { href: '/provider', label: 'Overview', icon: LayoutDashboard },
      { href: '/provider/nodes', label: 'My Nodes', icon: Server },
      { href: '/provider/nodes/register', label: 'Add a Machine', icon: PlusCircle },
      { href: '/provider/usage', label: 'Served Usage', icon: BarChart3 },
    ],
  },
  {
    title: 'Money',
    links: [
      { href: '/provider/earnings', label: 'Earnings & Payouts', icon: Wallet },
      { href: '/provider/transactions', label: 'Ledger', icon: Receipt },
    ],
  },
  { title: 'Account', links: [{ href: '/provider/settings', label: 'Settings', icon: Settings }] },
];

export const operatorSections: Section[] = [
  {
    links: [
      { href: '/operator', label: 'Overview', icon: LayoutDashboard },
      { href: '/operator/nodes', label: 'All Nodes', icon: Server },
      { href: '/operator/deployments', label: 'All Deployments', icon: Activity },
      { href: '/operator/models', label: 'Model Catalog', icon: Box },
      { href: '/operator/usage', label: 'Network Usage', icon: BarChart3 },
    ],
  },
  {
    title: 'Finance',
    links: [
      { href: '/operator/pricing', label: 'Pricing', icon: Tag },
      { href: '/operator/payouts', label: 'Payouts', icon: Banknote },
      { href: '/operator/reconciliation', label: 'Reconciliation', icon: Scale },
      { href: '/operator/transactions', label: 'Ledger', icon: Receipt },
    ],
  },
  { title: 'Security', links: [{ href: '/operator/audit', label: 'Audit Log', icon: ScrollText }] },
];

const ROLE_LABEL: Record<string, string> = { customer: 'Customer', provider: 'Provider', operator: 'Operator', admin: 'Admin' };

export function useNavLinks() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const role = user?.role;
  const sections = role === 'provider' ? providerSections : role === 'customer' ? customerSections : operatorSections;
  const links = sections.flatMap((s) => s.links);
  // Most specific match wins, so /provider/nodes/register does not also highlight /provider/nodes.
  const active = links
    .filter((l) => pathname === l.href || pathname.startsWith(l.href + '/'))
    .sort((a, b) => b.href.length - a.href.length)[0];
  return { user, role, sections, links, active, logout, roleLabel: ROLE_LABEL[role ?? ''] ?? '' };
}

function NavItem({ link, active }: { link: NavLink; active: boolean }) {
  const Icon = link.icon;
  return (
    <Link
      href={link.href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'group flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] transition-colors',
        active
          ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground shadow-[inset_0_0_0_1px_var(--sidebar-border)]'
          : 'text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground',
      )}
    >
      <Icon className={cn('size-4 shrink-0', active ? 'text-brand' : 'opacity-60 group-hover:opacity-100')} />
      <span className="truncate">{link.label}</span>
    </Link>
  );
}

export function Sidebar() {
  const { user, sections, active, logout, roleLabel } = useNavLinks();
  return (
    <aside className="hidden h-full w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
      <div className="flex h-14 items-center px-4">
        <Logo />
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-3">
        {sections.map((section, i) => (
          <div key={section.title ?? i}>
            {section.title && (
              <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">{section.title}</p>
            )}
            <ul className="space-y-0.5">
              {section.links.map((link) => (
                <li key={link.href}>
                  <NavItem link={link} active={link.href === active?.href} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-1.5 py-1.5">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand to-fuchsia-500 text-xs font-semibold uppercase text-white">
            {user?.email?.charAt(0)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium">{user?.email}</p>
            <p className="text-[11px] text-muted-foreground">{roleLabel}</p>
          </div>
          <ThemeToggle />
          <button
            type="button"
            onClick={() => logout()}
            aria-label="Sign out"
            title="Sign out"
            className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}

/** Top bar: page context on desktop; logo, controls and a scrollable nav strip on small screens. */
export function TopBar() {
  const { links, active, logout, roleLabel } = useNavLinks();
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="flex h-14 items-center justify-between gap-3 px-4 sm:px-8">
        <div className="md:hidden">
          <Logo />
        </div>
        <p className="hidden items-center gap-2 text-[13px] text-muted-foreground md:flex">
          <span>{roleLabel}</span>
          <span className="text-border">/</span>
          <span className="font-medium text-foreground">{active?.label ?? 'Dashboard'}</span>
        </p>
        <div className="flex items-center gap-1 md:hidden">
          <ThemeToggle />
          <button type="button" onClick={() => logout()} aria-label="Sign out" className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent">
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-4 pb-2 md:hidden">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={cn('whitespace-nowrap rounded-md px-2.5 py-1 text-[13px]', l.href === active?.href ? 'bg-muted font-medium' : 'text-muted-foreground')}
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
