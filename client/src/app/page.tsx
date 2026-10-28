import { CTA } from '@/components/landing/CTA';
import { Failover } from '@/components/landing/Failover';
import { Features } from '@/components/landing/Features';
import { Footer } from '@/components/landing/Footer';
import { Header } from '@/components/landing/Header';
import { HeroSection } from '@/components/landing/HeroSection';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { LiveStats } from '@/components/landing/LiveStats';
import { PricingSection } from '@/components/landing/PricingSection';
import { Status } from '@/components/landing/Status';
import { SponsoredSlot } from '@/components/sponsorship/SponsoredSlot';
import { STRUCTURED_DATA } from '@/lib/seo';

// JSON.stringify output is escaped for '<' so the data cannot close the script element.
const jsonLd = JSON.stringify(STRUCTURED_DATA).replace(/</g, '\\u003c');

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd }} />
      <Header />
      <main className="flex-1">
        <HeroSection />
        <LiveStats />
        <Features />
        <HowItWorks />
        <Failover />
        <PricingSection />
        <SponsoredSlot placement="landing" title="From our partners" className="mx-auto -mt-16 mb-16 max-w-3xl px-4 sm:px-6" />
        <Status />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
