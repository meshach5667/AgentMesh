'use client';

import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '@/providers/ThemeProvider';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      className={cn(
        'relative rounded-full text-muted-foreground hover:text-foreground transition-all duration-300 hover:bg-secondary/80 border border-transparent hover:border-border/60',
        className
      )}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      aria-label="Toggle theme"
    >
      <Sun
        className={cn(
          'h-[1.15rem] w-[1.15rem] transition-transform duration-500 ease-in-out text-amber-400',
          theme === 'dark' ? 'rotate-0 scale-100' : 'rotate-90 scale-0 absolute'
        )}
      />
      <Moon
        className={cn(
          'h-[1.15rem] w-[1.15rem] transition-transform duration-500 ease-in-out text-blue-500',
          theme === 'light' ? 'rotate-0 scale-100' : '-rotate-90 scale-0 absolute'
        )}
      />
      <span className="sr-only">Toggle theme</span>
    </Button>
  );
}
