import { create } from 'zustand';
import type { User } from '../types/user';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (role?: 'provider' | 'customer') => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  login: (role = 'provider') => set({
    isAuthenticated: true,
    user: {
      id: 'mock-user-id',
      email: `${role}@example.com`,
      role: role,
      created_at: new Date().toISOString(),
      is_active: true
    },
    token: 'mock-token'
  }),
  logout: () => set({ user: null, token: null, isAuthenticated: false })
}));
