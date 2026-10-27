import type { MetadataRoute } from 'next';
import { DOC_PAGES } from '@/lib/docs';
import { SITE_URL } from '@/lib/seo';

export default function sitemap(): MetadataRoute.Sitemap {
  const pages: { path: string; priority: number; changeFrequency: 'weekly' | 'monthly' }[] = [
    { path: '/', priority: 1, changeFrequency: 'weekly' },
    { path: '/docs', priority: 0.8, changeFrequency: 'weekly' },
    ...DOC_PAGES.map((p) => ({ path: p.href, priority: 0.7, changeFrequency: 'monthly' as const })),
    { path: '/register', priority: 0.5, changeFrequency: 'monthly' },
    { path: '/login', priority: 0.3, changeFrequency: 'monthly' },
  ];
  return pages.map(({ path, priority, changeFrequency }) => ({
    url: `${SITE_URL}${path === '/' ? '' : path}`,
    changeFrequency,
    priority,
  }));
}
