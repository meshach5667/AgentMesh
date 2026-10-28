// Mirrors server/app/services/sponsorship_service.py and the /sponsored and /admin/ads endpoints.
export type Placement = 'landing' | 'docs' | 'customer_dashboard' | 'provider_dashboard';
export type SponsorCategory =
  | 'gpu_cloud'
  | 'ai_inference'
  | 'model_hosting'
  | 'cloud_infrastructure'
  | 'data_center'
  | 'developer_tools'
  | 'ai_tools'
  | 'gpu_hardware'
  | 'infrastructure';
export type CampaignStatus = 'draft' | 'active' | 'paused' | 'ended';
/** sponsored: a labelled sponsored listing, resource or banner; referral: a labelled outbound referral link. */
export type CampaignKind = 'sponsored' | 'referral';

export interface SponsoredItem {
  id: string;
  kind: CampaignKind;
  /** Shown on the item: "Sponsored" or "Referral link". */
  label: string;
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
  kind: CampaignKind;
  referral_code?: string | null;
  utm_campaign?: string | null;
}

export interface Campaign
  extends Required<Omit<CampaignInput, 'body' | 'image_url' | 'starts_at' | 'ends_at' | 'referral_code' | 'utm_campaign'>> {
  id: string;
  body: string | null;
  image_url: string | null;
  starts_at: string | null;
  ends_at: string | null;
  referral_code: string | null;
  utm_campaign: string | null;
  status: CampaignStatus;
  impressions: number;
  clicks: number;
  ctr: number | null;
  serving: boolean;
  last_30_days: { impressions: number; clicks: number };
  created_at: string;
}
