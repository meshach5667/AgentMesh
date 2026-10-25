// Mirrors server/app/services/sponsorship_service.py and the /sponsored and /admin/ads endpoints.
export type Placement = 'landing' | 'docs' | 'customer_dashboard' | 'provider_dashboard';
export type SponsorCategory = 'ai_tools' | 'gpu_hardware' | 'infrastructure';
export type CampaignStatus = 'draft' | 'active' | 'paused' | 'ended';
export type SponsorPricingModel = 'cpm' | 'cpc' | 'flat';

export interface SponsoredItem {
  id: string;
  sponsor: string;
  category: SponsorCategory;
  headline: string;
  body: string | null;
  cta_label: string;
  image_url: string | null;
  token: string;
  /** API path (under the control plane origin) that counts the click and redirects to the sponsor. */
  click_path: string;
}

export interface SponsoredSlot {
  placement: Placement;
  enabled: boolean;
  items: SponsoredItem[];
}

export interface AdSettings {
  enabled: boolean;
  placements: { key: Placement; label: string; enabled: boolean; max_items: number }[];
  updated_at: string;
}

export interface CampaignInput {
  name: string;
  sponsor: string;
  category: SponsorCategory;
  headline: string;
  body?: string | null;
  cta_label?: string;
  target_url: string;
  image_url?: string | null;
  placements: Placement[];
  starts_at?: string | null;
  ends_at?: string | null;
  weight?: number;
  pricing_model: SponsorPricingModel;
  rate: string;
  budget?: string | null;
}

export interface Campaign extends Required<Omit<CampaignInput, 'body' | 'image_url' | 'starts_at' | 'ends_at' | 'budget'>> {
  id: string;
  body: string | null;
  image_url: string | null;
  starts_at: string | null;
  ends_at: string | null;
  budget: string | null;
  status: CampaignStatus;
  impressions: number;
  clicks: number;
  ctr: number | null;
  earned: string;
  serving: boolean;
  last_30_days: { impressions: number; clicks: number };
  created_at: string;
}
