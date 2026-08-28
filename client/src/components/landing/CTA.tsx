import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Terminal } from 'lucide-react';

export function CTA() {
  return (
    <section className="py-24 relative overflow-hidden border-t border-border/50">
      <div className="absolute inset-0 bg-blue-500/5"></div>
      <div className="container relative z-10 px-6 mx-auto text-center max-w-4xl">
        <h2 className="text-4xl md:text-6xl font-bold tracking-tight mb-8">
          Join the autonomous network.
        </h2>
        <p className="text-xl text-muted-foreground mb-12 max-w-2xl mx-auto">
          Whether you have idle GPUs to monetize or models to deploy, AgentMesh provides the economic and technical protocol to make it happen.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
          <Link href="/register">
            <Button size="lg" className="h-14 px-10 text-lg bg-white text-black hover:bg-gray-200">
              Deploy a Model <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
          <Link href="/register?role=provider">
            <Button variant="outline" size="lg" className="h-14 px-10 text-lg bg-background hover:bg-secondary">
              <Terminal className="mr-2 h-5 w-5 text-blue-500" /> Start Earning
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
}
