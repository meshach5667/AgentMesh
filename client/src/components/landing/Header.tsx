import Link from 'next/link';
import { Network } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function Header() {
  return (
    <header className="fixed top-0 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-50">
      <div className="container flex h-16 items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2">
          <Network className="h-6 w-6 text-blue-500" />
          <span className="font-bold text-lg tracking-tight">AgentMesh</span>
        </Link>
        <nav className="hidden md:flex gap-6">
          <Link href="#how-it-works" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">How it Works</Link>
          <Link href="#network" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">Network</Link>
          <Link href="#economics" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">Economics</Link>
        </nav>
        <div className="flex items-center gap-4">
          <Link href="/login">
            <Button variant="ghost" size="sm">Log in</Button>
          </Link>
          <Link href="/register">
            <Button size="sm" className="bg-white text-black hover:bg-gray-200">Start Building</Button>
          </Link>
        </div>
      </div>
    </header>
  );
}
