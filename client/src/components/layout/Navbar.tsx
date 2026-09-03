'use client';
import React from 'react';
import Link from 'next/link';
import { Network, LogOut, Bell } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

export function Navbar() {
  const { logout } = useAuth();

  return (
    <nav className="h-14 border-b border-border bg-background/80 backdrop-blur-xl flex items-center justify-between px-6 z-10 sticky top-0">
      <div className="flex items-center">
        <Link href="/" className="flex items-center gap-2">
          <Network className="h-5 w-5 text-blue-500" />
          <span className="font-bold text-lg tracking-tight">AgentMesh</span>
        </Link>
      </div>
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
          <Bell className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => logout()}
          className="text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center gap-2"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign Out</span>
        </Button>
      </div>
    </nav>
  );
}
