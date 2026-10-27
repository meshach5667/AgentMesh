import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/providers/QueryProvider';
import { ThemeProvider } from '@/providers/ThemeProvider';
import { SITE_DESCRIPTION, SITE_NAME, SITE_TITLE, SITE_URL } from '@/lib/seo';
import { cn } from '@/lib/utils';

const sans = Geist({ subsets: ['latin'], variable: '--font-geist-sans' });
const mono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono' });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: SITE_TITLE, template: '%s · AgentMesh' },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  keywords: [
    'open-weight models',
    'LLM hosting',
    'decentralized GPU compute',
    'OpenAI-compatible API',
    'Llama',
    'Qwen',
    'Mistral',
    'Ollama',
    'model deployment',
    'rent out GPU',
  ],
  authors: [{ name: 'Obed Meshach', url: 'https://github.com/meshach5667' }],
  creator: 'Obed Meshach',
  publisher: SITE_NAME,
  category: 'technology',
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    siteName: SITE_NAME,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: '/',
    locale: 'en_US',
  },
  twitter: { card: 'summary_large_image', title: SITE_TITLE, description: SITE_DESCRIPTION },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-image-preview': 'large', 'max-snippet': -1, 'max-video-preview': -1 },
  },
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#090F1D' },
  ],
  colorScheme: 'light dark',
};

// Applied before first paint so the page never flashes the wrong theme.
const themeScript = `try{var t=localStorage.getItem('theme');if(!t){t=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'}document.documentElement.classList.add(t)}catch(e){document.documentElement.classList.add('dark')}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={cn(sans.variable, mono.variable)}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ThemeProvider>
          <QueryProvider>{children}</QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
