'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Copy, Loader2, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { errorMessage } from '@/lib/errors';
import { homeFor } from '@/lib/roles';
import { useAuth } from '@/hooks/useAuth';
import { Field, inputClass, submitClass } from './AuthShell';

/** Group a base32 secret in fours so it is easy to type into an authenticator app. */
export function groupSecret(secret: string): string {
  return secret.replace(/(.{4})/g, '$1 ').trim();
}

/** Turn on TOTP two-factor authentication. Staff land here until they have it; anyone can use it. */
export function MfaSetup() {
  const { user, initialize, logout } = useAuth();
  const router = useRouter();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);

  if (user?.mfa_enabled && !user.mfa_verified) {
    // Already enrolled but this session skipped the second factor (it predates enrolment): sign in again.
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-semibold tracking-[-0.045em]">Sign in again</h1>
        <p className="text-sm text-muted-foreground">Two-factor authentication is on for this account. Sign in again and enter a code from your authenticator app.</p>
        <button type="button" className={submitClass} onClick={() => { logout(); router.replace('/login'); }}>
          Go to sign in
        </button>
      </div>
    );
  }

  const start = async () => {
    setBusy(true);
    try {
      setSetup((await api.post('/auth/mfa/setup')).data);
    } catch (err) {
      toast.error(errorMessage(err, 'Could not start setup'));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post('/auth/mfa/enable', { code });
      await initialize();
      toast.success('Two-factor authentication is on');
      router.replace(homeFor(user?.role));
    } catch (err) {
      toast.error(errorMessage(err, 'That code did not work'));
      setCode('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <p className="mb-3 flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground">
        <ShieldCheck className="size-4" /> Account security
      </p>
      <h1 className="text-3xl font-semibold tracking-[-0.045em]">Turn on two-factor authentication</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {user?.mfa_required
          ? 'Operator accounts need a second factor before operator features work.'
          : 'Protect your account with a code from an authenticator app.'}{' '}
        Use any TOTP app, such as Google Authenticator, Microsoft Authenticator, 1Password or Aegis.
      </p>

      {!setup ? (
        <button type="button" onClick={start} disabled={busy} className={`${submitClass} mt-8`}>
          {busy ? <Loader2 className="size-4 animate-spin" /> : null}
          Set up authenticator app
        </button>
      ) : (
        <form onSubmit={confirm} className="mt-8 space-y-5">
          <Field label="1. Add this key to your app">
            <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2">
              <code className="flex-1 break-all font-mono text-sm tracking-wider">{groupSecret(setup.secret)}</code>
              <button
                type="button"
                aria-label="Copy key"
                onClick={() => navigator.clipboard?.writeText(setup.secret).then(() => toast.success('Key copied'))}
                className="text-muted-foreground hover:text-foreground"
              >
                <Copy className="size-4" />
              </button>
            </div>
          </Field>
          <p className="text-xs text-muted-foreground">
            On a phone, you can open{' '}
            <a href={setup.otpauth_uri} className="underline underline-offset-4">
              this setup link
            </a>{' '}
            instead. Keep the key private; anyone with it can generate your codes.
          </p>
          <Field label="2. Enter the 6-digit code it shows">
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              required
              className={inputClass}
            />
          </Field>
          <button type="submit" disabled={busy || code.length !== 6} className={submitClass}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : null}
            Turn on
          </button>
        </form>
      )}
    </div>
  );
}
