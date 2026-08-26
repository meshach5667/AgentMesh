import { create } from 'zustand';
import type { User } from '../types/user';
interface AuthState { user: User | null; token: string | null; isAuthenticated: boolean; login: () => void; logout: () => void; }
export const useAuthStore = create<AuthState>((set) => ({ user: null, token: null, isAuthenticated: false, login: () => set({ isAuthenticated: true }), logout: () => set({ user: null, token: null, isAuthenticated: false }) }));