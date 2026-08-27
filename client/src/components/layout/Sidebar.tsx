'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '../../lib/utils';
import { useAuth } from '../../hooks/useAuth';
import { 
  LayoutDashboard, Server, Activity, DollarSign, 
  Box, CreditCard, Network
} from 'lucide-react';

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const role = user?.role || 'provider';

  const providerLinks = [
    { href: '/provider', label: 'Overview', icon: LayoutDashboard },
    { href: '/provider/nodes', label: 'My Nodes', icon: Server },
    { href: '/provider/earnings', label: 'Earnings', icon: DollarSign },
    { href: '/provider/transactions', label: 'Transactions', icon: Activity },
  ];

  const customerLinks = [
    { href: '/customer', label: 'Overview', icon: LayoutDashboard },
    { href: '/customer/models', label: 'Model Catalog', icon: Box },
    { href: '/customer/deployments', label: 'Deployments', icon: Activity },
    { href: '/customer/wallet', label: 'Wallet', icon: CreditCard },
    { href: '/customer/transactions', label: 'Transactions', icon: Activity },
  ];

  const operatorLinks = [
    { href: '/operator', label: 'Network', icon: Network },
    { href: '/operator/nodes', label: 'All Nodes', icon: Server },
    { href: '/operator/deployments', label: 'All Deployments', icon: Activity },
    { href: '/operator/models', label: 'Models', icon: Box },
    { href: '/operator/transactions', label: 'Transactions', icon: Activity },
  ];

  const links = role === 'provider' ? providerLinks : role === 'customer' ? customerLinks : operatorLinks;

  return (
    <aside className="w-64 border-r border-gray-800 bg-gray-900 hidden md:block">
      <div className="h-full px-3 py-4 overflow-y-auto">
        <ul className="space-y-2 font-medium">
          {links.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href || pathname.startsWith(link.href + '/');
            return (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className={cn(
                    "flex items-center p-2 rounded-lg group",
                    isActive ? "bg-blue-600/10 text-blue-500" : "text-gray-300 hover:bg-gray-800 hover:text-white"
                  )}
                >
                  <Icon className="w-5 h-5 mr-3" />
                  <span>{link.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
