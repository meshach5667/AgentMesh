import { HardwareInfo } from '../../../../components/nodes/HardwareInfo';
import { PricingForm } from '../../../../components/nodes/PricingForm';
import { MetricsGauge } from '../../../../components/charts/MetricsGauge';

export default async function NodeDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Node: {id}</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricsGauge value={45} label="CPU Usage" />
        <MetricsGauge value={80} label="RAM Usage" />
        <MetricsGauge value={12} label="GPU Usage" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <HardwareInfo hardware={{ cpu_model: 'AMD Ryzen 9', cpu_cores: 16, ram_gb: 64, storage_gb: 2000, gpu_model: 'RTX 4090', gpu_count: 1, gpu_vram_gb: 24, os_info: 'Ubuntu 22.04' }} />
        <PricingForm onSave={() => {}} />
      </div>
    </div>
  );
}
