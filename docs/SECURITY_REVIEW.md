# Security and Operational Review (Phase 7)

Scope: the control-plane API, the dashboard, billing and payments, and the production configuration, as of
2026-10-21. The worker's isolation was reviewed in earlier phases ([WORKER.md](WORKER.md)). This review is by
the engineer who built the feature, not an independent audit. It records what was checked, what was fixed,
and what remains.

## Fixed in this phase

| Finding | Risk | Fix |
| --- | --- | --- |
| No throttling on login and registration | Password guessing and credential stuffing | Limit per client address and per email (`AUTH_RATE_LIMIT_PER_MINUTE`, default 10/min), shared across replicas when Redis is used; 429 with `Retry-After` |
| Paystack keys not covered by log redaction | Secret key in logs if an error message contains it | `sk_/pk_ test/live` keys are redacted like API keys and bearer tokens |
| No security response headers | Clickjacking, MIME sniffing | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `COOP` on the API (plus HSTS outside dev); headers on the dashboard via `next.config.ts` |
| HTTP allowed for the public API URL in production | API keys sent in cleartext | Startup refuses a non-https `PUBLIC_BASE_URL` outside dev/test |
| Two money paths that moved balances without ledger entries (`payment_service.settle_usage`, legacy workload settlement) | Balances that cannot be reconciled | Removed. All balance changes go through `ledger_service` with idempotency keys |
| Checkout redirect followed whatever URL the API returned | Open redirect if the API response were tampered with | The dashboard redirects only to `https://*.paystack.com` |
| Providers report token counts, which set their own earnings | A malicious provider inflates bills | Billable output tokens are capped at the response bytes the gateway counted itself; see the residual risks below |
| A live Paystack key could be enabled by accident | Real money in an untested setup | Live keys need `PAYSTACK_ALLOW_LIVE=true`; malformed keys are rejected at startup |

## Payment controls reviewed

- **Webhooks.**
  - The HMAC-SHA512 signature of the raw body is checked in constant time.
  - An optional allowlist restricts source IPs.
  - Each event is processed once (unique event key in `payment_events`).
  - Payloads are not stored; they contain customer contact and card details.
- **Crediting.**
  - Wallets are credited only when the amount and currency match the payment record. A mismatch goes to
    `REVIEW` and is never credited automatically.
  - Payments move with a compare-and-set, and ledger postings have unique idempotency keys. Webhook, verify
    and reconciliation therefore cannot double-credit. Tests cover repeated webhook deliveries, verify after
    a webhook, a webhook after verify, and reconciliation of late payments; they do not run truly concurrent
    requests.
- **Payouts.**
  - Funds are held at request time.
  - Concurrent requests that would overdraw the wallet are rolled back.
  - Payouts are marked `PENDING` before Paystack is called, so a payout is never sent twice.
  - Unknown outcomes (timeouts) keep the hold until Paystack answers.
  - Operator approval is on by default.
  - Only the last four digits of bank accounts are stored.
- **Authorization.**
  - Top-ups are limited to customers and payouts to providers. Pricing, payout decisions and reconciliation
    are staff only.
  - Charges are visible only to the paying customer, the credited provider, or staff.
  - Cross-tenant access is tested.
- **Ledger.** Balance changes are atomic SQL increments. Reconciliation checks that every balance equals its
  ledger entries, that every charge splits exactly, that top-ups are credited once, and that payout holds
  match payout states.

## Residual risks (not fixed)

1. **Runtime-reported usage.**
   - Token counts come from the provider's machine. The byte cap bounds inflation of output tokens but does
     not prevent it.
   - Input tokens are not bounded.
   - READY time relies on worker reports plus control-plane health tracking. A provider could keep a broken
     runtime "READY": customers then see failed requests, but resource time is still charged.

   Mitigations: operators can set token prices to zero (resource-only pricing). The provider failure rates
   in usage data should be reviewed. Customer refunds need a ledger correction feature, which doesn't exist
   yet.
2. **Session tokens in `localStorage`.** Any XSS in the dashboard could steal a session. The dashboard sends
   no Content-Security-Policy yet. Next.js's inline scripts make a strict CSP non-trivial.
3. **Per-email throttling allows a 1-minute lockout.** Anyone who knows an address can slow down its owner.
4. **No multi-factor authentication** for operators or anyone else. Operator accounts can approve payouts and
   change prices.
5. **Customer balances may go below zero** by up to one billing interval of usage before deployments are
   stopped. The platform carries that exposure; providers are credited in full.
6. **Charges with no node** (`node_id` NULL) are not protected by the unique constraint on PostgreSQL, where
   NULLs never collide. The billing watermark's compare-and-set still prevents double rating. No current
   code path creates such charges.
7. **The audit log is not tamper-evident.** Anyone with database access can change it.
8. **Default database credentials in `docker-compose.yml`.** Postgres is on the internal network only, but
   the password should be changed. The API does not enforce this.
9. **Secrets live in environment variables.** No secret manager is integrated.
10. **The Docker worker needs the Docker socket**, which is root-equivalent on the provider's host (see
    [WORKER.md](WORKER.md)).

## Not verified

- **Real Paystack API calls.** No Paystack keys were available while building this. The client follows
  Paystack's documented API and is tested against a fake with the documented response shapes. Webhook
  signatures were tested end to end over HTTP. Run `scripts/paystack_smoke.py` with a test key before
  relying on it.
- **Migration 009 and the backup/restore round trip on PostgreSQL.** There is no PostgreSQL on the
  development machine. The migration was rendered offline and reviewed; both run in CI.
- **Multi-replica billing with Redis.** Concurrency safety rests on the database (compare-and-set and unique
  keys), which the tests exercise on SQLite only.
