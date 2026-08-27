import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { QueryProvider } from '@/providers/QueryProvider';
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: 'AgentMesh - Decentralized AI Compute Marketplace',
  description: 'Deploy AI models on a decentralized compute network',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("dark", inter.variable, jetbrainsMono.variable)}>
      <body className={cn("min-h-screen bg-background text-foreground antialiased", inter.className)}>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
