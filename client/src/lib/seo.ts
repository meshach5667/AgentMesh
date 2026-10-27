import type { Metadata } from 'next';
import { DASHBOARD_URL, REPO_URL } from '@/lib/config';
import { DOC_PAGES } from '@/lib/docs';

export const SITE_NAME = 'AgentMesh';
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || DASHBOARD_URL).replace(/\/$/, '');
export const SITE_TITLE = 'AgentMesh — Open-weight AI models on community compute';
export const SITE_DESCRIPTION =
  'Deploy open-weight AI models such as Llama, Qwen and Mistral on machines contributed by independent providers, ' +
  'and call them through an OpenAI-compatible API. Providers earn from their spare GPUs and CPUs.';

/** For pages that must stay out of search results (dashboards, account flows). */
export const NO_INDEX: Metadata['robots'] = { index: false, follow: false };

/** The site-wide share image (app/opengraph-image.png). Pages that set their own openGraph must list it again. */
const SHARE_IMAGE = { url: '/opengraph-image.png', width: 1200, height: 630, alt: 'AgentMesh: open-weight AI models on community compute' };

/** Title, description and canonical URL for a docs page, from its DOC_PAGES entry. */
export function docMetadata(href: string): Metadata {
  const page = DOC_PAGES.find((p) => p.href === href);
  if (!page) throw new Error(`No DOC_PAGES entry for ${href}`);
  return {
    title: page.title,
    description: page.summary,
    alternates: { canonical: href },
    openGraph: { title: `${page.title} · AgentMesh docs`, description: page.summary, url: href, images: [SHARE_IMAGE] },
    twitter: { card: 'summary_large_image', title: `${page.title} · AgentMesh docs`, description: page.summary, images: [SHARE_IMAGE] },
  };
}

/** schema.org description of AgentMesh for search engines, rendered as JSON-LD on the landing page. */
export const STRUCTURED_DATA = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${SITE_URL}/#organization`,
      name: SITE_NAME,
      url: SITE_URL,
      logo: `${SITE_URL}/icons/icon-512.png`,
      sameAs: [REPO_URL],
    },
    {
      '@type': 'WebSite',
      '@id': `${SITE_URL}/#website`,
      name: SITE_NAME,
      url: SITE_URL,
      description: SITE_DESCRIPTION,
      publisher: { '@id': `${SITE_URL}/#organization` },
      inLanguage: 'en',
    },
    {
      '@type': 'SoftwareApplication',
      name: SITE_NAME,
      url: SITE_URL,
      description: SITE_DESCRIPTION,
      applicationCategory: 'DeveloperApplication',
      operatingSystem: 'Web, Linux, macOS',
      publisher: { '@id': `${SITE_URL}/#organization` },
    },
  ],
};
