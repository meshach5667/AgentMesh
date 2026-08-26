import { ModelCard } from '../../../components/models/ModelCard';
import type { Model } from '../../../types';

export default function CustomerModels() {
  const dummyModels: Model[] = [
    { id: 'llama3-8b', name: 'Llama 3 8B', version: '1.0', runtime: 'vLLM', source: 'huggingface', minimum_vram: 16, minimum_ram: 32, minimum_cpu: 8, storage_requirement: 20, is_approved: true }
  ];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Model Catalog</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {dummyModels.map(m => <ModelCard key={m.id} model={m} />)}
      </div>
    </div>
  );
}
