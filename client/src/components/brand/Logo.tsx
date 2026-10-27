import Link from 'next/link';
import { cn } from '@/lib/utils';

/** The official AgentMesh symbol (public/logos): four interlocking bars around a blue node. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="255 255 514 514" aria-hidden className={cn('size-7', className)}>
      <g className="fill-[#090F1D] dark:fill-white">
        <rect x="255" y="255" width="316" height="158" rx="27" />
        <rect x="611" y="255" width="158" height="316" rx="27" />
        <rect x="255" y="453" width="158" height="316" rx="27" />
        <rect x="453" y="611" width="316" height="158" rx="27" />
      </g>
      <polygon points="512,454 570,512 512,570 454,512" fill="#2E6CFF" />
    </svg>
  );
}

export function Logo({ href = '/', className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn('flex items-center gap-2.5 font-semibold tracking-tight', className)} aria-label="AgentMesh home">
      <LogoMark />
      <span className="text-[15px]">AgentMesh</span>
    </Link>
  );
}
