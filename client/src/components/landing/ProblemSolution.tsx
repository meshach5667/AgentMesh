import { ServerCrash, Bot, Network} from 'lucide-react';
import { Card } from '@/components/ui/card';

export function ProblemSolution() {
  return (
    <section className="py-24" id="economics">
      <div className="container px-6 mx-auto">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl md:text-5xl font-bold mb-6 tracking-tight">The AI Infrastructure Gap</h2>
          <p className="text-lg text-muted-foreground">
            Machine learning deployment is currently bottlenecked by centralized cloud monopolies, manual orchestration, and wasted idle compute.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-12 lg:gap-24 items-center">
          <div className="space-y-8">
            <Card className="p-6 border-red-500/20 bg-red-500/5 shadow-none relative overflow-hidden group">
              <div className="absolute top-0 left-0 w-1 h-full bg-red-500/50"></div>
              <div className="flex gap-4">
                <div className="mt-1 bg-background p-2 rounded-md border border-border">
                  <ServerCrash className="w-6 h-6 text-red-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-2">The Old Way</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">
                    Developers hunt for scarce cloud GPUs, manually configure instances, handle failovers by hand, and pay premium markups while providers lock them into ecosystems.
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-6 border-blue-500/20 bg-blue-500/5 shadow-none relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-blue-500/50"></div>
              <div className="flex gap-4">
                <div className="mt-1 bg-background p-2 rounded-md border border-border">
                  <Network className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-2">The AgentMesh Way</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">
                    Specify your model and constraints. Our autonomous agents instantly discover optimal nodes, deploy the workload, manage execution, and stream usage analytics securely.
                  </p>
                </div>
              </div>
            </Card>
          </div>

          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-2xl blur-3xl -z-10"></div>
            <Card className="p-1 border-border/50 bg-background/50 backdrop-blur-sm overflow-hidden">
              <div className="bg-black rounded-lg p-6 border border-border/50 font-mono text-sm">
                <div className="flex items-center gap-2 mb-4 text-muted-foreground border-b border-border/50 pb-4">
                  <Bot className="w-4 h-4" />
                  <span>Agent orchestrator logs</span>
                </div>
                <div className="space-y-3 opacity-90">
                  <p><span className="text-blue-400">agent</span> <span className="text-gray-500">→</span> Analyzing deployment request: Llama-3-8b</p>
                  <p><span className="text-gray-500">sys</span> <span className="text-gray-500">→</span> Required: 1x GPU, &gt;16GB VRAM, Latency &lt;50ms</p>
                  <p className="pl-4 border-l border-gray-800"><span className="text-yellow-400">querying</span> registry for capable nodes...</p>
                  <p className="pl-4 border-l border-gray-800"><span className="text-green-400">found</span> 42 candidates. Filtering by price & reliability.</p>
                  <p><span className="text-blue-400">agent</span> <span className="text-gray-500">→</span> Selected Node-7x9a (RTX 4090, $0.22/hr)</p>
                  <p><span className="text-purple-400">exec</span> <span className="text-gray-500">→</span> Sending signed deployment manifest...</p>
                  <p><span className="text-green-500">success</span> <span className="text-gray-500">→</span> Workload active. Streaming health telemetry.</p>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </section>
  );
}
