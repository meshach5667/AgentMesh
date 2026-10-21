# Operating AgentMesh

This guide is for people who run the AgentMesh control plane: the API, the dashboard, and PostgreSQL. It
covers configuration, payments, monitoring, backups, and recovery. Customer and provider workflows are in
[GETTING_STARTED.md](GETTING_STARTED.md); workers are covered in [WORKER.md](WORKER.md).

## 1. Production configuration

Anything other than `ENVIRONMENT=dev|development|test|testing` counts as production. In production the API
refuses to start unless:

- `SECRET_KEY` is random and at least 32 characters (`openssl rand -hex 32`);
- `CORS_ORIGINS` lists explicit origins (JSON array or comma-separated; no `*`);
- `PUBLIC_BASE_URL` uses `https://`;
- `PAYSTACK_SECRET_KEY`, if set, is a test key (`sk_test_…`). A live key needs `PAYSTACK_ALLOW_LIVE=true`.

Unpaid test credits are always disabled in production.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL (`postgresql+asyncpg://…`). Change the default `agentmesh:agentmesh` credentials. Hosted databases that require TLS need `?ssl=require` on the URL (or `&ssl=require` when it already has query parameters). |
| `PUBLIC_BASE_URL`, `FRONTEND_URL` | Public https URLs of the API and the dashboard. Paystack returns customers to `$FRONTEND_URL/customer/wallet`. |
| `COORDINATION_BACKEND=redis`, `REDIS_URL` | Required when you run more than one API replica (shared rate limits, tunnel routing, and one leader for the background jobs). |
| `BILLING_CURRENCY` | The single platform currency (default `NGN`). Choose it before taking real payments; it cannot be mixed. |
| `BILLING_INTERVAL_SECONDS`, `BILLING_MIN_PREPAID_HOURS` | How often usage is rated into charges (300 s), and how many hours of a reservation a customer must be able to afford to deploy (1). |
| `PAYSTACK_SECRET_KEY`, `PAYSTACK_WEBHOOK_IPS` | Paystack key, and optionally Paystack's webhook source IPs (JSON list). |
| `TOPUP_MIN_AMOUNT`, `TOPUP_MAX_AMOUNT`, `PAYOUT_MIN_AMOUNT`, `PAYOUTS_REQUIRE_APPROVAL` | Payment limits. Keep approval on until you trust your fraud controls. |
| `AUTH_RATE_LIMIT_PER_MINUTE` | Login and registration attempts per minute, per client address and per email (default 10). |
| `METRICS_TOKEN` | Bearer token for `GET /metrics`. Empty disables the endpoint. |
| `NEXT_PUBLIC_API_URL` | Dashboard API URL (`https://<api host>/api/v1`), baked in when the dashboard is **built**. Defaults to the hosted API. |

Put the API behind a TLS-terminating reverse proxy. Run uvicorn with `--proxy-headers` (as
`docker-compose.yml` does) so rate limits, the audit log, and the webhook IP check see real client addresses.
Restrict `--forwarded-allow-ips` to the proxy's address if the API port is reachable from elsewhere.

`docker-compose.yml` runs `alembic upgrade head` before starting the API. When running the API any other way,
apply migrations first.

### First start

1. Create the first operator account: `python scripts/create_operator.py ops@example.com` (see
   [GETTING_STARTED.md](GETTING_STARTED.md#operators)).
2. Approve models and artifacts under **Model Catalog**.
3. Publish prices under **Pricing**. Until a price list exists, usage is measured but not charged.

## 2. Payments (Paystack)

AgentMesh uses Paystack for customer top-ups and provider payouts. It runs in **test mode** unless you
explicitly allow a live key.

1. In the Paystack dashboard (test mode):
   - Copy the secret key into `PAYSTACK_SECRET_KEY`.
   - Set the webhook URL to `https://<api>/api/v1/payments/paystack/webhook`.
2. Check the integration against Paystack's real test API. This calls Paystack directly; no AgentMesh
   server is needed:

   ```bash
   cd server
   PAYSTACK_SECRET_KEY=sk_test_... python scripts/paystack_smoke.py          # banks, checkout, verify
   PAYSTACK_SECRET_KEY=sk_test_... python scripts/paystack_smoke.py --pay    # also pay with a test card
   ```

3. Make a top-up from the dashboard and confirm that the webhook arrives. **Reconciliation** should show no
   open top-ups, and **Ledger** should show the deposit.
4. Payouts use Paystack Transfers. They need a funded Paystack balance and, for API use, transfer OTP turned
   off in the Paystack dashboard. If OTP is on, payouts stop at `OTP_REQUIRED`.

How money moves:

- **Top-ups** are credited only after Paystack reports success, and only if the amount and currency match.
  Each is credited exactly once, whether the confirmation arrives by webhook, by the customer's return to the
  dashboard, or by reconciliation. A mismatch is held as `REVIEW` and is never credited automatically.
- **Charges.** Every billing interval, each deployment's READY time and runtime-reported tokens are priced
  with the version in force. The customer's wallet is debited; the provider's wallet is credited after the
  platform fee.
- **Running out of credit.** A customer's balance can drop below zero by at most one billing interval. Their
  deployments are then stopped with `INSUFFICIENT_FUNDS`.
- **Payouts** are held from the provider's balance as soon as they are requested. An operator approves them
  under **Payouts**, which sends the Paystack transfer. A failed, reversed, or rejected payout returns the
  held amount.
- **Unknown outcomes.** If a transfer's outcome is unknown, for example after a timeout, the payout stays
  `PENDING` and the money stays held. Reconciliation then asks Paystack for the result.

## 3. Monitoring

| Endpoint | Use |
| --- | --- |
| `GET /health` | Liveness. The process is up. |
| `GET /health/ready` | Readiness: database, plus Redis when used. Returns 503 if either fails. Use it for load balancers and the compose healthcheck. |
| `GET /metrics` | Prometheus text format, with `Authorization: Bearer $METRICS_TOKEN`. Exposes request counts by status class, and nodes, deployments, payments and payouts by status. |
| `GET /api/v1/admin/overview` | The operator dashboard's numbers, including nodes whose heartbeats are overdue. |
| `GET /api/v1/admin/reconciliation` | Ledger invariants and open payment items. |

Logs are JSON lines with a request id. Secrets (API keys, node credentials, bearer tokens, and Paystack keys)
are redacted before writing.

Suggested alerts:

- `/health/ready` failing for more than 1 minute.
- A rising `agentmesh_http_requests_total{status="5xx"}`.
- `agentmesh_payouts{status="OTP_REQUIRED"} > 0`.
- Payouts `PENDING` for more than an hour.
- Any `ok: false` from reconciliation. Run it at least daily.
- `Billing failed for deployment` or `Background job … failed` in the logs.
- The overview's `nodes_heartbeat_overdue` staying above 0. This means the background monitor isn't running.

## 4. Backups

```bash
cd server
DATABASE_URL=postgresql+asyncpg://… KEEP=14 ops/backup_db.sh /var/backups/agentmesh   # e.g. hourly from cron
```

`ops/backup_db.sh` writes a compressed `pg_dump` (custom format, mode 0600) and keeps the newest `KEEP`
files. Dumps contain account and ledger data. Store copies off the host, encrypted.

Test a restore at least monthly:

```bash
createdb agentmesh_restore
DATABASE_URL=postgresql+asyncpg://…/agentmesh_restore ops/restore_db.sh /var/backups/agentmesh/agentmesh-<ts>.dump
```

The restore script refuses a database that isn't empty. CI runs a backup-and-restore round trip on every
push; see the `migrations-check` job in `.github/workflows/ci.yml`. Worker release signing keys and the
`.env` file are not in the database: back them up separately.

## 5. Recovery runbooks

**API process crash or restart.**
- Workers reconnect on their own; their deployments keep serving.
- Background jobs resume on the next interval. Billing rates any missed time from each deployment's
  watermark, so nothing is lost and nothing is charged twice.

**Database restore.**
1. Stop the API.
2. Restore into a new database and point `DATABASE_URL` at it.
3. Run `alembic upgrade head`, then start the API.
4. Run reconciliation (`POST /api/v1/admin/reconciliation/run`). It re-checks open top-ups and payouts with
   Paystack. Anything paid after the backup is credited when Paystack confirms it.
5. Expect worker state to be ahead of the restored database. Deployments created after the backup are
   unknown to the control plane, and workers drop them on reconciliation.

**Webhooks were down** (outage, wrong URL, or a bad key). Nothing is lost:

- Customers returning from checkout trigger verification.
- Reconciliation, run every 10 minutes when payments are enabled, settles top-ups and payouts older than
  `RECONCILE_AFTER_MINUTES`.

**Payout stuck in `OTP_REQUIRED` or `PENDING`.**
1. Check the transfer in the Paystack dashboard.
2. For OTP, turn off transfer OTP or finalize the transfer in Paystack.
3. Run reconciliation. It confirms the final state and sets `reconciled_at`. Never refund a pending payout by
   hand: the transfer may still complete.

**Reconciliation reports a discrepancy.**
1. Stop payouts: leave `PAYOUTS_REQUIRE_APPROVAL=true` and approve nothing.
2. Use the audit log (`/operator/audit`) and the ledger to find the cause.
3. Do not edit balances directly. Ledger entries are the source of truth, and balances must equal them.
4. Corrections need a code path that posts ledger entries. None exists yet, so escalate to engineering.

**Rotating secrets.**
- Changing `SECRET_KEY` signs everyone out. API keys and node credentials are unaffected, because they are
  stored as hashes.
- Rotate the Paystack key in the Paystack dashboard, then update `PAYSTACK_SECRET_KEY`. Webhooks are signed
  with the new key from then on.
- Revoke a compromised node under **All Nodes**.

**A node misbehaves** (wrong answers, or inflated token counts). Revoke it. Its deployments move to other
nodes. Charges already settled stay in the ledger. Refunds aren't automated yet: a refund needs a ledger
posting.

## 6. Scaling out

To run several API replicas:

- Set `COORDINATION_BACKEND=redis` on all of them.
- One replica at a time runs the background jobs (leader lock in Redis).
- Billing and payment updates are safe to run concurrently anyway. They use compare-and-set updates and
  unique keys, and wallet updates are atomic in SQL.
