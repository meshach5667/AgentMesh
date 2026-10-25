'use client';

import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { reportImpression, useSponsored } from '@/hooks/useSponsorship';
import { CATEGORY_LABEL, clickUrl, dismiss, dismissedIds } from '@/lib/sponsorship';
import { cn } from '@/lib/utils';
import type { Placement, SponsoredItem } from '@/types';

function Item({ item, placement, onDismiss }: { item: SponsoredItem; placement: Placement; onDismiss: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const counted = useRef(false);
  const href = clickUrl(item.click_path);

  // An impression is reported once, when at least half of the item has been on screen.
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !counted.current) {
          counted.current = true;
          void reportImpression(item.id, placement, item.token);
          observer.disconnect();
        }
      },
      { threshold: 0.5 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [item.id, item.token, placement]);

  if (!href) return null;
  return (
    <div ref={ref} className="relative rounded-lg border border-dashed border-border bg-muted/30 p-3 text-sm" data-testid="sponsored-item">
      <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
        <span className="rounded border border-border px-1.5 py-px font-medium">Sponsored</span>
        <span>{CATEGORY_LABEL[item.category]}</span>
        <button type="button" onClick={onDismiss} className="ml-auto rounded p-0.5 hover:bg-muted" aria-label={`Hide sponsored item from ${item.sponsor}`}>
          <X className="size-3.5" />
        </button>
      </div>
      <a href={href} target="_blank" rel="sponsored noopener noreferrer nofollow" className="group block space-y-1">
        <p className="font-medium group-hover:underline group-hover:underline-offset-4">{item.headline}</p>
        {item.body && <p className="text-xs text-muted-foreground">{item.body}</p>}
        <p className="text-xs text-muted-foreground">
          {item.sponsor} · <span className="underline underline-offset-4">{item.cta_label}</span>
        </p>
      </a>
    </div>
  );
}

/** A clearly labelled sponsored slot. Renders nothing unless an operator turned advertising and this slot on; viewers
 * can hide individual items. No cookies or third-party scripts: impressions and clicks go to AgentMesh only. */
export function SponsoredSlot({ placement, className, title }: { placement: Placement; className?: string; title?: string }) {
  const { data } = useSponsored(placement);
  // Items arrive only after a client-side fetch, so reading storage here cannot cause a hydration mismatch.
  const [hidden, setHidden] = useState<string[]>(() => (typeof window === 'undefined' ? [] : dismissedIds()));
  const items = (data?.items ?? []).filter((i) => !hidden.includes(i.id));
  if (!data?.enabled || items.length === 0) return null;
  return (
    <aside className={cn('space-y-2', className)} aria-label="Sponsored">
      {title && <p className="text-xs font-medium text-muted-foreground">{title}</p>}
      {items.map((item) => (
        <Item
          key={item.id}
          item={item}
          placement={placement}
          onDismiss={() => {
            dismiss(item.id);
            setHidden((h) => [...h, item.id]);
          }}
        />
      ))}
    </aside>
  );
}
