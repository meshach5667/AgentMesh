export type UserRole = 'provider' | 'customer' | 'operator' | 'admin';
export interface User {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  mfa_enabled?: boolean;
  /** From /auth/me: this account must use a second factor, and whether this session completed it. */
  mfa_required?: boolean;
  mfa_verified?: boolean;
}
export interface Provider { id: string; user_id: string; display_name: string | null; }
export interface Customer { id: string; user_id: string; }