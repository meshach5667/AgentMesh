import { Terminal, Box, Zap } from 'lucide-react';
import { Card } from '@/components/ui/card';

export function HowItWorks() {
  const steps = [
    {
      title: 'Connect Compute',
      description: 'Run the lightweight Node Agent on your hardware. It automatically detects GPUs, benchmarks capabilities, and registers to the decentralized network.',
      icon: Terminal,
      step: '01'
    },
    {
      title: 'Deploy Models',
      description: 'Select from approved OSS models or specify your own container. Define your VRAM, latency, and budget requirements in a simple manifest.',
      icon: Box,
      step: '02'
    },
    {
      title: 'Agents Operate',
      description: 'Our AI orchestrator constantly monitors the mesh. It matches workloads to optimal nodes, handles failures, and guarantees execution.',
      icon: Zap,
      step: '03'
    }
  ];

  return (
    <section className="py-24 bg-secondary/20" id="how-it-works">
      <div className="container px-6 mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-5xl font-bold mb-6 tracking-tight">How the Mesh Operates</h2>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((s, i) => (
            <Card key={i} className="p-8 border-border bg-background shadow-sm hover:border-blue-500/30 transition-colors relative group overflow-hidden">
              <div className="absolute top-0 right-0 p-8 text-8xl font-black text-secondary/30 group-hover:text-secondary/50 transition-colors -z-10 -mt-8 -mr-4 select-none">
                {s.step}
              </div>
              <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center mb-6 text-blue-500 border border-blue-500/20">
                <s.icon className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold mb-3">{s.title}</h3>
              <p className="text-muted-foreground leading-relaxed">
                {s.description}
              </p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
