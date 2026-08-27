import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Terminal } from 'lucide-react';
import { MeshVisualization } from './MeshVisualization';

export function Hero() {
  return (
    <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden">
      <div className="container px-6 mx-auto">
        <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-24">
          <div className="flex-1 text-center lg:text-left z-10">
            <div className="inline-flex items-center rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-sm text-blue-400 mb-6">
              <span className="flex w-2 h-2 rounded-full bg-blue-500 mr-2 animate-pulse"></span>
              Mainnet Beta is Live
            </div>

            <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
              AI infrastructure <br className="hidden md:block" />
              <span className="text-muted-foreground">that runs itself.</span>
            </h1>

            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto lg:mx-0">
              AgentMesh connects underutilized compute with AI workloads.
              Deploy models instantly while autonomous agents handle placement, scaling, and recovery.
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start">
              <Link href="/register">
                <Button size="lg" className="h-12 px-8 bg-white text-black hover:bg-gray-200 text-base">
                  Deploy a Model <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href="/register?role=provider">
                <Button variant="outline" size="lg" className="h-12 px-8 text-base border-border hover:bg-secondary">
                  <Terminal className="mr-2 h-4 w-4" /> Become a Node
                </Button>
              </Link>
            </div>

            <div className="mt-10 flex items-center justify-center lg:justify-start gap-8 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <div className="w-1 h-4 bg-green-500 rounded-full"></div>
                <span>99.9% Uptime</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1 h-4 bg-blue-500 rounded-full"></div>
                <span>Decentralized</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1 h-4 bg-purple-500 rounded-full"></div>
                <span>Agentic</span>
              </div>
            </div>
          </div>

          <div className="flex-1 w-full max-w-2xl lg:max-w-none">
            <MeshVisualization />
          </div>
        </div>
      </div>
    </section>
  );
}
