import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Server} from 'lucide-react';

export function MarketplacePreview() {
  const providers = [
    { id: '1', name: 'Node-7x9a', gpu: '1x RTX 4090', vram: '24 GB', price: '$0.25/hr', status: 'Available', uptime: '99.9%' },
    { id: '2', name: 'US-East-Alpha', gpu: '4x A100', vram: '320 GB', price: '$4.10/hr', status: 'Available', uptime: '99.99%' },
    { id: '3', name: 'Desk-Node-02', gpu: '1x RTX 3090', vram: '24 GB', price: '$0.18/hr', status: 'Busy', uptime: '97.5%' },
  ];

  return (
    <section className="py-24" id="network">
      <div className="container px-6 mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-end mb-12 gap-6">
          <div>
            <h2 className="text-3xl md:text-5xl font-bold mb-4 tracking-tight">Open Compute Marketplace</h2>
            <p className="text-lg text-muted-foreground max-w-2xl">
              Transparent pricing driven by supply and demand. No hidden egress fees or platform lock-in.
            </p>
          </div>
        </div>

        <Card className="border-border bg-background shadow-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-muted-foreground uppercase bg-secondary/30 border-b border-border">
                <tr>
                  <th className="px-6 py-4 font-medium">Provider / Node</th>
                  <th className="px-6 py-4 font-medium">Hardware</th>
                  <th className="px-6 py-4 font-medium">VRAM</th>
                  <th className="px-6 py-4 font-medium">Reliability</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium text-right">Price</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono">
                {providers.map((p, i) => (
                  <tr key={i} className="hover:bg-secondary/10 transition-colors">
                    <td className="px-6 py-4 flex items-center gap-3">
                      <Server className="w-4 h-4 text-muted-foreground" />
                      {p.name}
                    </td>
                    <td className="px-6 py-4">{p.gpu}</td>
                    <td className="px-6 py-4">{p.vram}</td>
                    <td className="px-6 py-4">{p.uptime}</td>
                    <td className="px-6 py-4">
                      <Badge variant="outline" className={p.status === 'Available' ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-amber-500/10 text-amber-500 border-amber-500/20'}>
                        {p.status}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-right font-bold text-foreground">
                      {p.price}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </section>
  );
}
