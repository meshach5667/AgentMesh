import { Header } from '@/components/landing/Header';
import { Hero } from '@/components/landing/Hero';
import { LiveStats } from '@/components/landing/LiveStats';
import { ProblemSolution } from '@/components/landing/ProblemSolution';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { MarketplacePreview } from '@/components/landing/MarketplacePreview';
import { CTA } from '@/components/landing/CTA';
import { Footer } from '@/components/landing/Footer';

export default function Home() {
  return (
    <div className="min-h-screen bg-background flex flex-col selection:bg-blue-500/20 selection:text-blue-200">
      <Header />
      <main className="flex-1">
        <Hero />
        <LiveStats />
        <ProblemSolution />
        <HowItWorks />
        <MarketplacePreview />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
