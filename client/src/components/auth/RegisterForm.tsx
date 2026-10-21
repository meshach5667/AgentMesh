'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, Box, Eye, EyeOff, Loader2, Server } from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import type { UserRole } from '@/types/user';
import { useAuth } from '../../hooks/useAuth';
import { Field, inputClass, submitClass } from './AuthShell';

const ROLES = [
  { value: 'customer' as const, icon: Box, title: 'Deploy models', body: 'Run open-weight models behind an API' },
  { value: 'provider' as const, icon: Server, title: 'Provide compute', body: 'Earn from your idle machines' },
];

export function RegisterForm({ initialRole = 'customer' }: { initialRole?: 'provider' | 'customer' }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState<'provider' | 'customer'>(initialRole);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const { register, error, clearError } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    setSubmitting(true);
    try {
      await register(email, password, role as UserRole);
      toast.success('Account created');
      router.push(role === 'provider' ? '/provider' : '/customer');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">Free to sign up. You only pay for what you deploy.</p>
      {error && (
        <div role="alert" className="mt-6 rounded-lg border border-destructive/25 bg-destructive/[0.06] px-3 py-2.5 text-sm text-destructive">
          {error}
        </div>
      )}
      <form onSubmit={handleSubmit} className="mt-8 space-y-4">
        <fieldset>
          <legend className="mb-1.5 text-[13px] font-medium">I want to</legend>
          <div className="grid grid-cols-2 gap-2">
            {ROLES.map(({ value, icon: Icon, title, body }) => (
              <button
                key={value}
                type="button"
                aria-pressed={role === value}
                onClick={() => setRole(value)}
                className={cn(
                  'rounded-lg border p-3 text-left transition-all',
                  role === value ? 'border-brand/60 bg-brand-soft/60 ring-4 ring-brand/10' : 'border-border hover:bg-accent',
                )}
              >
                <Icon className={cn('size-4', role === value ? 'text-brand' : 'text-muted-foreground')} />
                <p className="mt-2 text-[13px] font-medium">{title}</p>
                <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{body}</p>
              </button>
            ))}
          </div>
        </fieldset>
        <Field label="Email">
          <input type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} required className={inputClass} />
        </Field>
        <Field label="Password">
          <span className="relative block">
            <input
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className={`${inputClass} pr-10`}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </span>
        </Field>
        <Field label="Confirm password">
          <input type="password" autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required className={inputClass} />
        </Field>
        <button type="submit" disabled={submitting} className={submitClass}>
          {submitting ? <Loader2 className="size-4 animate-spin" /> : null}
          {submitting ? 'Creating account…' : 'Create account'}
          {!submitting && <ArrowRight className="size-4" />}
        </button>
      </form>
      <p className="mt-8 text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
