'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '../../lib/utils';
import { useAuth } from '../../hooks/useAuth';
import { 
  LayoutDashboard, Server, Activity, DollarSign, 
  Box, CreditCard, Network, Settings, Bot, Store
} from 'lucide-react';

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const role = user?.role || 'provider';

  const providerLinks = [
    { href: '/provider', label: 'Overview', icon: LayoutDashboard },
    { href: '/provider/nodes', label: 'Network Nodes', icon: Server },
    { href: '/provider/earnings', label: 'Earnings', icon: DollarSign },
    { href: '/provider/transactions', label: 'Transactions', icon: Activity },
    { href: '/provider/settings', label: 'Settings', icon: Settings },
  ];

  const customerLinks = [
    { href: '/customer', label: 'Overview', icon: LayoutDashboard },
    { href: '/customer/models', label: 'Models', icon: Box },
    { href: '/customer/deployments', label: 'Deployments', icon: Activity },
    { href: '/customer/marketplace', label: 'Marketplace', icon: Store },
    { href: '/customer/agent-activity', label: 'Agent Activity', icon: Bot },
    { href: '/customer/wallet', label: 'Wallet', icon: CreditCard },
    { href: '/customer/transactions', label: 'Transactions', icon: Activity },
    { href: '/customer/settings', label: 'Settings', icon: Settings },
  ];

  const operatorLinks = [
    { href: '/operator', label: 'Overview', icon: LayoutDashboard },
    { href: '/operator/network', label: 'Network Map', icon: Network },
    { href: '/operator/nodes', label: 'All Nodes', icon: Server },
    { href: '/operator/deployments', label: 'All Deployments', icon: Activity },
    { href: '/operator/models', label: 'Models', icon: Box },
    { href: '/operator/transactions', label: 'Ledger', icon: Activity },
    { href: '/operator/settings', label: 'Settings', icon: Settings },
  ];

  const links = role === 'provider' ? providerLinks : role === 'customer' ? customerLinks : operatorLinks;

  return (
    <aside className="w-64 border-r border-border bg-sidebar h-full flex flex-col">
      <div className="flex-1 overflow-y-auto py-6">
        <div className="px-4 mb-4">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-2">
            {role === 'provider' ? 'Compute Provider' : role === 'customer' ? 'AI Workloads' : 'Operator Control'}
          </p>
        </div>
        <ul className="space-y-1 px-3 font-medium text-sm">
          {links.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href || (link.href !== '/' && pathname.startsWith(link.href + '/'));
            return (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className={cn(
                    "flex items-center px-3 py-2 rounded-md group transition-colors",
                    isActive
                      ? "bg-sidebar-primary/20 text-sidebar-primary-foreground font-semibold"
                      : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
                  )}
                >
                  <Icon className={cn("w-4 h-4 mr-3", isActive ? "text-sidebar-primary-foreground" : "text-sidebar-foreground/50 group-hover:text-sidebar-foreground")} />
                  <span>{link.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="p-4 border-t border-border mt-auto">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center border border-border">
            <span className="text-xs font-bold text-foreground">
              {user?.email?.charAt(0).toUpperCase() || 'U'}
            </span>
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium truncate text-foreground">{user?.email || 'User Account'}</span>
            <span className="text-xs text-muted-foreground capitalize">{role}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
