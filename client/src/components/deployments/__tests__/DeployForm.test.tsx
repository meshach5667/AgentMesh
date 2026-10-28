import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AxiosError, AxiosHeaders } from 'axios';
import { DeployForm } from '../DeployForm';
import api from '@/lib/api';
import type { Model, ModelArtifact } from '@/types';

const push = jest.fn();
jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));
jest.mock('@/lib/api', () => ({ __esModule: true, default: { post: jest.fn(), get: jest.fn() } }));
const post = api.post as jest.Mock;
const get = api.get as jest.Mock;
const OFFERS = [
  {
    id: 'prov-1',
    display_name: 'Lagos GPU Co',
    description: null,
    machines_available: 2,
    gpu_machines: 0,
    runtimes: ['ollama'],
    free_machines: 0,
    prices: [{ currency: 'NGN', cpu_core_hour: '3' }],
    payment_methods: ['bank_transfer'],
    accepts_payment_arrangement: true,
  },
];
// POST /deployments creates; POST /deployments/quote prices it. Tests set what the create call does.
const deploy = jest.fn();
const quote = jest.fn();
const deployCalls = () => post.mock.calls.filter(([url]) => url === '/deployments');

const QUOTE = {
  currency: 'NGN',
  min_prepaid_hours: 1,
  by_runtime: [
    {
      runtime: 'ollama',
      requirements: { cpu_cores: 1, ram_mb: 1024, disk_mb: 768, vram_mb: 0 },
      eligible_nodes: 3,
      over_price_limit: 1,
      cheapest: {
        cpu_core_hour: '3',
        ram_gb_hour: '20',
        vram_gb_hour: '0',
        input_tokens_per_million: '500',
        output_tokens_per_million: '900',
        currency: 'NGN',
      },
      hourly: '23',
      other_currency: 0,
      provider: { id: 'prov-1', display_name: 'Lagos GPU Co', description: null, payment: null },
    },
    {
      runtime: 'llamacpp',
      requirements: { cpu_cores: 1, ram_mb: 768, disk_mb: 768, vram_mb: 0 },
      eligible_nodes: 0,
      over_price_limit: 2,
      cheapest: null,
      hourly: null,
      other_currency: 0,
      provider: null,
    },
  ],
};

const artifact = (runtime: ModelArtifact['runtime'], over: Partial<ModelArtifact> = {}): ModelArtifact => ({
  id: runtime,
  runtime,
  source_type: runtime === 'ollama' ? 'ollama' : 'huggingface',
  reference: runtime === 'ollama' ? 'qwen2.5:0.5b' : 'Qwen/Qwen2.5-0.5B-Instruct-GGUF',
  revision: null,
  file: null,
  sha256: null,
  size_bytes: null,
  format: null,
  quantization: null,
  min_ram_mb: runtime === 'ollama' ? 1024 : 768,
  min_disk_mb: 768,
  min_vram_mb: 0,
  min_cpu_cores: 1,
  gpu_required: false,
  requirements_estimated: true,
  is_enabled: true,
  last_ready_at: null,
  ...over,
});

const model = { id: 'm1', name: 'Qwen', license: 'Apache-2.0', artifacts: [artifact('llamacpp'), artifact('ollama')] } as Model;

function renderForm(m: Model = model) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DeployForm model={m} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  post.mockReset();
  push.mockReset();
  deploy.mockReset();
  quote.mockReset();
  quote.mockResolvedValue({ data: QUOTE });
  get.mockReset();
  get.mockResolvedValue({ data: OFFERS });
  post.mockImplementation((url: string, body: unknown) => (url === '/deployments/quote' ? quote(body) : deploy(body)));
});

it('requires the trust acknowledgement before deploying', () => {
  renderForm();
  const deploy = screen.getByRole('button', { name: 'Deploy' });
  expect(deploy).toBeDisabled();
  expect(screen.getByText(/provider can see the model, its memory, and every prompt/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox', { name: /I understand the provider can see/ }));
  expect(deploy).toBeEnabled();
});

it('submits the chosen runtime and config with an idempotency key, then opens the deployment', async () => {
  deploy.mockResolvedValue({ data: { id: 'dep-1' } });
  renderForm();
  fireEvent.click(screen.getByRole('radio', { name: /^llama\.cpp/ }));
  fireEvent.change(screen.getByLabelText('Context window (tokens)'), { target: { value: '4096' } });
  // Only the chosen runtime is estimated: 768 MB + 128 MB for the larger context.
  expect(screen.getByText(/896 MB RAM/)).toBeInTheDocument();
  expect(screen.queryByText(/1 GB RAM/)).toBeNull();
  fireEvent.click(screen.getByRole('checkbox', { name: /I understand/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Deploy' }));
  await waitFor(() => expect(push).toHaveBeenCalledWith('/customer/deployments/dep-1'));
  const [, body] = deployCalls()[0];
  expect(body).toMatchObject({ model_id: 'm1', runtime: 'llamacpp', config: { num_ctx: 4096, require_gpu: false } });
  expect(body.idempotency_key).toEqual(expect.any(String));
});

it('lists automatic runtimes in preference order and omits runtime for automatic', async () => {
  deploy.mockResolvedValue({ data: { id: 'dep-2' } });
  renderForm();
  expect(screen.getByText(/Try Ollama, then llama\.cpp/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox', { name: /I understand/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Deploy' }));
  await waitFor(() => expect(deploy).toHaveBeenCalled());
  expect(deployCalls()[0][1].runtime).toBeUndefined();
});

it('explains a 503 per runtime', async () => {
  const headers = new AxiosHeaders();
  deploy.mockRejectedValue(
    new AxiosError('x', 'ERR', undefined, undefined, {
      status: 503,
      statusText: '',
      headers,
      config: { headers },
      data: {
        detail: {
          code: 'no_eligible_node',
          reasons: { insufficient_capacity: 1, unsupported_runtime: 1 },
          by_runtime: {
            ollama: { message: 'x', reasons: { insufficient_capacity: 1 } },
            llamacpp: { message: 'y', reasons: { unsupported_runtime: 1 } },
          },
        },
      },
    }),
  );
  renderForm();
  fireEvent.click(screen.getByRole('checkbox', { name: /I understand/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Deploy' }));
  expect(await screen.findByText('No node can run this deployment right now')).toBeInTheDocument();
  expect(screen.getByText(/1 node: not enough free CPU, memory, disk or GPU memory/)).toBeInTheDocument();
  expect(screen.getByText(/1 node: runtime not installed on the node/)).toBeInTheDocument();
  expect(push).not.toHaveBeenCalled();
});

it('refuses models without an enabled artifact', () => {
  renderForm({ ...model, artifacts: [artifact('ollama', { is_enabled: false })] });
  expect(screen.getByText(/no enabled runtime artifact/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Deploy' })).toBeNull();
});

it('shows the cheapest machine price per runtime and why a runtime has none', async () => {
  renderForm();
  expect(await screen.findByTestId('hourly-ollama')).toHaveTextContent(
    /NGN\s?23\.00 per hour while ready, plus NGN\s?500\.00 in \/ NGN\s?900\.00 out per million tokens, on the cheapest of 3 machines within your limits \(Lagos GPU Co\)/,
  );
  expect(screen.getByTestId('hourly-llamacpp')).toHaveTextContent('2 machines fit but charge more than your price limits');
});

it('sends price limits with the quote and the deployment', async () => {
  deploy.mockResolvedValue({ data: { id: 'dep-3' } });
  renderForm();
  fireEvent.change(screen.getByLabelText('Most per hour while ready'), { target: { value: '45.5' } });
  fireEvent.change(screen.getByLabelText('Most per million tokens'), { target: { value: '3000' } });
  await waitFor(() => expect(quote).toHaveBeenCalledWith(expect.objectContaining({ max_hourly_price: '45.5', max_token_price: '3000' })));
  fireEvent.click(screen.getByRole('checkbox', { name: /I understand/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Deploy' }));
  await waitFor(() => expect(deploy).toHaveBeenCalled());
  expect(deployCalls()[0][1]).toMatchObject({ max_hourly_price: '45.5', max_token_price: '3000' });
});

it('refuses an invalid price limit', () => {
  renderForm();
  fireEvent.change(screen.getByLabelText('Most per hour while ready'), { target: { value: '-3' } });
  fireEvent.click(screen.getByRole('checkbox', { name: /I understand/ }));
  expect(screen.getByRole('button', { name: 'Deploy' })).toBeDisabled();
});

it('sends the chosen provider, currency and failover policy', async () => {
  deploy.mockResolvedValue({ data: { id: 'dep-4' } });
  renderForm();
  expect(await screen.findByRole('option', { name: /Lagos GPU Co · 2 machines available/ })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'prov-1' } });
  fireEvent.change(screen.getByLabelText('Currency'), { target: { value: 'usd' } });
  fireEvent.click(screen.getByRole('radio', { name: /Ask me first/ }));
  fireEvent.click(screen.getByRole('checkbox', { name: /I understand/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Deploy' }));
  await waitFor(() => expect(deploy).toHaveBeenCalled());
  expect(deployCalls()[0][1]).toMatchObject({ provider_id: 'prov-1', currency: 'USD', failover_policy: 'manual' });
});
