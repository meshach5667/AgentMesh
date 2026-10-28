// Mirrors server/app/schemas/billing.py and provider.py. Decimal amounts arrive as strings.
// AgentMesh processes no payments: customers pay providers directly. Amounts here are providers' published prices
// and estimates of what usage costs at them.

/** A machine's price list, in the provider's chosen currency. */
export interface Prices {
  currency: string;
  cpu_core_hour: string;
  ram_gb_hour: string;
  vram_gb_hour: string;
  input_tokens_per_million: string;
  output_tokens_per_million: string;
}

export type PriceField = Exclude<keyof Prices, 'currency'>;

export const PRICE_FIELDS: { key: PriceField; label: string; unit: string }[] = [
  { key: 'cpu_core_hour', label: 'CPU core', unit: 'per hour' },
  { key: 'ram_gb_hour', label: 'Memory', unit: 'per GB-hour' },
  { key: 'vram_gb_hour', label: 'GPU memory', unit: 'per GB-hour' },
  { key: 'input_tokens_per_million', label: 'Input tokens', unit: 'per million' },
  { key: 'output_tokens_per_million', label: 'Output tokens', unit: 'per million' },
];

export type Rates = Prices;

export interface NodePriceVersion extends Prices {
  id: string;
  node_id: string;
  version: number;
  effective_from: string;
  created_at: string;
}

export interface NodePricing {
  node_id: string;
  /** What the machine charges new deployments now; null when it is free. */
  charging: Rates | null;
  history: NodePriceVersion[];
}

export interface DefaultPrices {
  prices: Prices | null;
  updated_machines: number;
}

export interface CurrencyMarket {
  currency: string;
  nodes: number;
  ranges: Partial<Record<PriceField, { min: string; max: string }>>;
}

export interface Market {
  nodes: number;
  free_nodes: number;
  currencies: CurrencyMarket[];
}

export type PaymentMethod = 'bank_transfer' | 'payment_link' | 'mobile_money' | 'invoice' | 'other';

export const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  bank_transfer: 'Bank transfer',
  payment_link: 'Payment link',
  mobile_money: 'Mobile money',
  invoice: 'Invoice',
  other: 'Other',
};

export interface PaymentLink {
  label: string;
  url: string;
}

/** How a provider takes payment. Shown by AgentMesh, never processed by it. */
export interface PaymentProfile {
  methods: PaymentMethod[];
  accepted_currencies: string[];
  instructions: string | null;
  links: PaymentLink[];
  terms: string | null;
  minimum_amount: string | null;
  minimum_currency: string | null;
  minimum_note: string | null;
}

export interface ProviderCard {
  id: string;
  display_name: string;
  description: string | null;
  payment: PaymentProfile | null;
}

export interface ProviderOffer {
  id: string;
  display_name: string;
  description: string | null;
  machines_available: number;
  gpu_machines: number;
  runtimes: string[];
  free_machines: number;
  prices: (Partial<Prices> & { currency: string })[];
  payment_methods: PaymentMethod[];
  accepts_payment_arrangement: boolean;
}

export interface ProviderDetail extends ProviderOffer {
  payment: PaymentProfile | null;
}

export interface RuntimeQuote {
  runtime: string;
  requirements: { cpu_cores: number; ram_mb: number; disk_mb: number; vram_mb: number };
  eligible_nodes: number;
  over_price_limit: number;
  other_currency: number;
  /** Rates of the machine placement would pick now (null: free, or no machine). */
  cheapest: Rates | null;
  /** Hourly price of the reservation there; null when no machine fits. */
  hourly: string | null;
  provider: ProviderCard | null;
}

export interface Quote {
  currency: string;
  by_runtime: RuntimeQuote[];
}

export interface DeploymentPricing {
  deployment_id: string;
  rates: Rates | null;
  hourly: string | null;
  placed_at: Record<string, string> | null;
  provider: ProviderCard | null;
  /** Quote this when paying the provider. */
  payment_reference: string;
}

export interface CostEstimate {
  id: string;
  deployment_id: string;
  node_id: string | null;
  provider_id: string | null;
  /** Short customer reference (providers match payments against it). */
  customer_ref: string | null;
  period_start: string;
  period_end: string;
  ready_seconds: number;
  cpu_cores: number;
  ram_mb: number;
  vram_mb: number;
  input_tokens: number;
  output_tokens: number;
  resource_amount: string;
  token_amount: string;
  amount: string;
  currency: string;
  rates: Record<string, string> | null;
  created_at: string;
}

export type EstimateScope = 'customer' | 'provider' | 'network';

export interface CostSummary {
  scope: EstimateScope;
  days: number;
  since: string;
  totals: { currency: string; amount: string; resource_amount: string; token_amount: string; ready_hours: number }[];
  by_day: { day: string; currency: string; amount: string; deployments: number }[];
}
