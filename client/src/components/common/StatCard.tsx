import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

export function StatCard({
  title,
  value,
  hint,
  icon: Icon,
  className,
}: {
  title: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  icon?: LucideIcon;
  className?: string;
}) {
  return (
    <div className={cn('rounded-2xl border border-border/80 bg-card p-5 shadow-soft transition-shadow hover:shadow-lifted', className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[13px] font-medium text-muted-foreground">{title}</p>
        {Icon && (
          <span className="flex size-9 items-center justify-center rounded-xl bg-brand/[0.08] text-brand">
            <Icon className="size-4" />
          </span>
        )}
      </div>
      <div className="mt-3 text-[30px] font-semibold tracking-[-0.04em] tabular-nums" data-testid={`stat-${title}`}>
        {value}
      </div>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
