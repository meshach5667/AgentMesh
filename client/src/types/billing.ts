// Mirrors server/app/schemas/billing.py. Decimal amounts arrive as strings.
export interface PricingRule {
  id: string;
  version: number;
  currency: string;
  cpu_core_hour: string;
  ram_gb_hour: string;
  vram_gb_hour: string;
  input_tokens_per_million: string;
  output_tokens_per_million: string;
  platform_fee_rate: string;
  effective_from: string;
  notes: string | null;
  created_at: string;
}

export interface Pricing {
  current: PricingRule | null;
  upcoming: PricingRule[];
  currency: string;
  min_prepaid_hours: number;
  billing_interval_seconds: number;
  default_platform_fee_rate: string;
  max_platform_fee_rate: string;
}

export interface Charge {
  id: string;
  deployment_id: string;
  node_id: string | null;
  /** Network price version (sets the commission); null when none was in force. */
  pricing_rule_id: string | null;
  /** The node's own price version, when it charged its provider's prices. */
  node_price_id: string | null;
  /** Unit prices applied, as decimal strings, plus source: "node" or "network". */
  rates: Record<string, string> | null;
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
  provider_amount: string;
  platform_fee: string;
  /** Commission rate the charge was split at; null on charges made before it was recorded. */
  platform_fee_rate: string | null;
  refunded_amount: string;
  currency: string;
  created_at: string;
}

export interface ChargeTotals {
  charges: number;
  gross: string;
  platform_fee: string;
  provider_share: string;
  resource_amount: string;
  token_amount: string;
  effective_fee_rate: string | null;
}

export type BillingScope = 'customer' | 'provider' | 'network';

export interface BillingSummary {
  scope: BillingScope;
  days: number;
  since: string;
  currency: string;
  totals: ChargeTotals;
}

export interface PaymentsConfig {
  enabled: boolean;
  provider: 'paystack' | null;
  mode: 'test' | 'live' | null;
  currency: string;
  topup_min: string;
  topup_max: string;
  payout_min: string;
  payouts_require_approval: boolean;
  test_credits: boolean;
}

export type PaymentStatus = 'INITIALIZED' | 'SUCCEEDED' | 'FAILED' | 'ABANDONED' | 'REVIEW';

export interface Payment {
  id: string;
  reference: string;
  amount: string;
  currency: string;
  status: PaymentStatus;
  provider_status: string | null;
  authorization_url: string | null;
  channel: string | null;
  failure_reason: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface Bank {
  name: string;
  code: string;
}

export interface PayoutAccount {
  bank_code: string;
  bank_name: string | null;
  account_name: string | null;
  account_last4: string;
  currency: string;
  updated_at: string;
}

export type PayoutStatus = 'REQUESTED' | 'PENDING' | 'OTP_REQUIRED' | 'SUCCEEDED' | 'FAILED' | 'REVERSED' | 'REJECTED';

export interface Payout {
  id: string;
  user_id: string;
  amount: string;
  currency: string;
  reference: string;
  status: PayoutStatus;
  failure_reason: string | null;
  decided_at: string | null;
  completed_at: string | null;
  reconciled_at: string | null;
  created_at: string;
}

export interface ReconciliationReport {
  ok: boolean;
  issues: ({ kind: string } & Record<string, unknown>)[];
  checked: { wallets: number; charges: number };
  open: { payments_initialized: number; payouts_awaiting_approval: number; payouts_in_flight: number };
  generated_at: string;
}

export type RefundStatus = 'PENDING' | 'SUCCEEDED' | 'FAILED';

export interface Refund {
  id: string;
  kind: 'charge' | 'topup';
  reference: string;
  user_id: string;
  charge_id: string | null;
  payment_id: string | null;
  amount: string;
  provider_amount: string;
  platform_fee: string;
  currency: string;
  reason: string;
  status: RefundStatus;
  provider_status: string | null;
  failure_reason: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AdminTopup extends Payment {
  user_email: string | null;
  refundable: string;
}

/** One day of revenue; network scope adds topups, payouts, card_refunds and sponsorship. */
export interface RevenuePoint {
  date: string;
  gross: string;
  platform_fee: string;
  provider_share: string;
  refunded: string;
  fee_reversed: string;
  clawback: string;
  topups?: string;
  payouts?: string;
  card_refunds?: string;
  sponsorship?: string;
}

export interface RevenueAnalytics {
  scope: BillingScope;
  days: number;
  since: string;
  currency: string;
  series: RevenuePoint[];
  totals: Omit<RevenuePoint, 'date'> & {
    net_platform_commission: string;
    net_provider_earnings: string;
    net_customer_spend: string;
    platform_revenue?: string;
  };
  breakdown: { id: string; label: string; charges: number; gross: string; platform_fee: string; provider_share: string }[];
  breakdown_by: 'deployment' | 'node' | 'provider';
}

/** A machine's price list, before the platform commission. Decimal strings. */
export interface Prices {
  cpu_core_hour: string;
  ram_gb_hour: string;
  vram_gb_hour: string;
  input_tokens_per_million: string;
  output_tokens_per_million: string;
}

export type PriceField = keyof Prices;

export const PRICE_FIELDS: { key: PriceField; label: string; unit: string }[] = [
  { key: 'cpu_core_hour', label: 'CPU core', unit: 'per hour' },
  { key: 'ram_gb_hour', label: 'Memory', unit: 'per GB-hour' },
  { key: 'vram_gb_hour', label: 'GPU memory', unit: 'per GB-hour' },
  { key: 'input_tokens_per_million', label: 'Input tokens', unit: 'per million' },
  { key: 'output_tokens_per_million', label: 'Output tokens', unit: 'per million' },
];

/** What a machine charges: its provider's own prices ("node") or the network prices ("network"). */
export interface Rates extends Prices {
  source: 'node' | 'network';
}

export interface NodePriceVersion extends Prices {
  id: string;
  node_id: string;
  version: number;
  currency: string;
  effective_from: string;
  created_at: string;
}

export interface NodePricing {
  node_id: string;
  currency: string;
  /** What the machine charges new deployments now; null when free. */
  charging: Rates | null;
  network: Rates | null;
  commission_rate: string;
  history: NodePriceVersion[];
}

export interface DefaultPrices {
  currency: string;
  prices: Prices | null;
  updated_machines: number;
}

export interface Market {
  currency: string;
  nodes: number;
  own_prices: number;
  ranges: Partial<Record<PriceField, { min: string; max: string }>>;
  network: Rates | null;
  commission_rate: string;
}

export interface RuntimeQuote {
  runtime: string;
  requirements: { cpu_cores: number; ram_mb: number; disk_mb: number; vram_mb: number };
  eligible_nodes: number;
  over_price_limit: number;
  cheapest: Rates | null;
  hourly: string | null;
  max_hourly_price: string | null;
  max_token_price: string | null;
}

export interface Quote {
  currency: string;
  min_prepaid_hours: number;
  by_runtime: RuntimeQuote[];
}

export interface DeploymentPricing {
  deployment_id: string;
  currency: string;
  rates: Rates | null;
  hourly: string | null;
  placed_at: Record<string, string> | null;
  commission_rate: string;
}
