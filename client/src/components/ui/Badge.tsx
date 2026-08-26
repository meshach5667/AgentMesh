import React from 'react';
import { cn } from '../../lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
        {
          'border-transparent bg-gray-700 text-gray-100': variant === 'default',
          'border-transparent bg-green-500/20 text-green-400': variant === 'success',
          'border-transparent bg-yellow-500/20 text-yellow-400': variant === 'warning',
          'border-transparent bg-red-500/20 text-red-400': variant === 'error',
          'border-transparent bg-blue-500/20 text-blue-400': variant === 'info',
        },
        className
      )}
      {...props}
    />
  );
}
