'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Search, Box, Zap, MemoryStick } from 'lucide-react';
import { useModels } from '@/hooks/useModels';

export default function CustomerModelsPage() {
  const { data: models, isLoading } = useModels();

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading model catalog...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Model Catalog</h1>
          <p className="text-muted-foreground">Select and deploy AI models to the decentralized mesh.</p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input type="search" placeholder="Search models..." className="pl-8 bg-background" />
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {models?.length ? models.map((model: import("@/types").ExtendedModel) => (
          <Card key={model.id} className="flex flex-col border-border/50 bg-background/50 backdrop-blur-sm hover:border-blue-500/30 transition-colors">
            <CardHeader>
              <div className="flex justify-between items-start mb-2">
                <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20">
                  {model.runtime}
                </Badge>
                <span className="text-xs font-mono text-muted-foreground">{model.version}</span>
              </div>
              <CardTitle className="flex items-center gap-2">
                <Box className="w-5 h-5 text-muted-foreground" />
                {model.name}
              </CardTitle>
              <CardDescription className="line-clamp-2">
                Standard inference workload for {model.name}. Automatically finds capable nodes.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1">
              <div className="space-y-3 text-sm">
                <div className="flex justify-between items-center py-1 border-b border-border/50">
                  <span className="text-muted-foreground flex items-center gap-2"><MemoryStick className="w-4 h-4"/> Min VRAM</span>
                  <span className="font-mono">{Math.round(model.minimum_vram / (1024 ** 3))} GB</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-border/50">
                  <span className="text-muted-foreground flex items-center gap-2"><Zap className="w-4 h-4"/> Hardware</span>
                  <span className="font-medium text-xs">{model.supported_gpu_families?.join(', ') || 'Any Compatible GPU'}</span>
                </div>
              </div>
            </CardContent>
            <CardFooter>
              <Button className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
                Configure & Deploy
              </Button>
            </CardFooter>
          </Card>
        )) : (
          <div className="col-span-full p-12 text-center border rounded-xl border-dashed border-border text-muted-foreground">
            No models available in the catalog currently.
          </div>
        )}
      </div>
    </div>
  );
}
