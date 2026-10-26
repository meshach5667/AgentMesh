# AgentMesh Data Handling

**Last updated:** 26 October 2026

What data AgentMesh holds, where, who can see it, how long it is kept and how it is deleted. Retention values are the defaults in `server/app/core/config.py`, enforced hourly by `server/app/services/retention_service.py` (tested in `server/tests/test_privacy.py`).

## Data classes

| Data | Where it lives | Who can see it | Retention | Deletion |
|---|---|---|---|---|
| **Prompts and outputs sent to deployments** (gateway) | **Not stored** by the control plane. Passes in memory through the API to the provider's machine and back | The customer; **the provider's machine processes it in plaintext** | Not stored | n/a. Tests inject canary strings and assert they never reach logs (`test_privacy.py`) |
| AI deployment agent: request text, plan, run events | MongoDB `ai_runs`, `ai_run_events` | The customer; staff | 90 days after the run finishes (`AI_RUN_RETENTION_DAYS`) | Customer: `DELETE /ai/deployments/{id}` for finished runs (reports counts); retention job |
| AI agent model calls: prompt, output | MongoDB `ai_inference_requests`; sent to the operator's internal inference machine (not a provider node) | Staff, the inference machine | Prompt erased when answered; output after 24 h (`AI_INFERENCE_RESULT_RETENTION_HOURS`); record deleted with its run | Retention job; run deletion |
| Account: email, role, password hash (Argon2id), MFA seed (AES-256-GCM, bound to the user) | MongoDB `users` | The user; staff see email and role | Life of the account | On request to the operator (no self-service account deletion yet; see Gaps) |
| Sessions: IP address, browser user agent, timestamps | MongoDB `auth_sessions`; refresh tokens as SHA-256 in `refresh_tokens` | Staff (investigations) | Until the session expires (max 14 days, `REFRESH_TOKEN_TTL_DAYS`), removed by a TTL index | Logout, logout-all |
| API keys | MongoDB `api_keys`, SHA-256 hash and prefix only | The owner sees the prefix | Until revoked; kept as revoked records | Revoke |
| Per-request usage: endpoint, status, duration, request and response sizes, reported token counts, request id | MongoDB `usage_records` | The customer (own); providers (requests served, no customer identity); staff | 400 days (`USAGE_RECORD_RETENTION_DAYS`) | Retention job |
| Charges, ledger, payments, refunds, payouts | MongoDB billing collections | The parties concerned; staff | **Kept**: financial records, never purged by the retention job | Corrections are new ledger entries, never edits |
| Payout bank account | Paystack holds the full number; AgentMesh keeps bank code and name, account name, last four digits and a recipient code | The provider; staff | Life of the account | On request |
| Payment card data | **Never touches AgentMesh** (Paystack checkout) | Paystack | Paystack's policy | — |
| Data sent to Paystack | Customer email at top-up; provider account number, bank code and name for payouts | Paystack | Paystack's policy | — |
| Provider node data: hardware (CPU, RAM, disk, OS, GPU), region, versions, metrics, heartbeats | MongoDB `nodes`, `node_hardware` | The provider; staff. Public statistics show counts only. The public marketplace lists node name, region and hardware | Life of the node | Revoke the node (record kept for billing history) |
| Deployment events (lifecycle history) | MongoDB `deployment_events` | The customer; staff | 180 days (`DEPLOYMENT_EVENT_RETENTION_DAYS`) | Retention job |
| Audit log (security and admin actions, failed logins with the email entered) | MongoDB `audit_logs` | Staff | 365 days (`AUDIT_LOG_RETENTION_DAYS`) | Retention job |
| Application logs (JSON lines: request id, status, events; no bodies) | Hosting platform's log service | Operators | The hosting platform's log retention | Platform |
| Sponsored-placement view tokens | MongoDB `sponsor_views` (hash only, no personal data) | — | 24 h (TTL index) | TTL |
| Node sessions, challenges | MongoDB `node_sessions`, `node_challenges` (hashes only) | — | Session 1 h, challenge 60 s (TTL indexes) | Revocation, TTL |

## What providers can technically see

A provider controls its own machine, so it can read:
- the full prompt and output of every request its node serves;
- the model files and the runtime's memory;
- the deployment id, model and resource limits in each command.

Providers do **not** receive the customer's name, email, account id or billing details. TLS and encryption at rest do not change any of this: decryption happens on the provider's machine. Workers delete per-deployment runtimes and workspaces when a deployment stops, fails or is moved; a dishonest provider could keep copies, which only contracts and removal from the network address.

## Backups

The operator's backup script (`server/ops/backup_db.sh`) keeps the 14 most recent archives. If it runs daily, deleted data can remain in backups for up to 14 days. Managed snapshots from the database provider follow that provider's schedule. Restored backups must be followed by a retention run before use.

## Training and third parties

Customer prompts, inputs and outputs are not used to train models and are not sent to any third party other than the provider node serving the request (and, for the AI deployment agent, the operator's own inference machine). Hugging Face receives only public repository lookups, with no customer data.

## Logging rules

- Logs carry identifiers, statuses, timings and error codes, never bodies. Secret patterns are redacted (`server/app/core/logging.py`).
- Security events (`agentmesh.security`) emit only allowlisted fields (`server/app/core/security_events.py`).
- Canary tests cover success, runtime failure, gateway crash, malformed input, failed login and bad tokens.

## Gaps

- No self-service account deletion; account deletion is done by the operator on request.
- Application log retention depends on the hosting plan and is not set by the code.
- Usage records are kept for 400 days for billing disputes. Shorten `USAGE_RECORD_RETENTION_DAYS` if that is not needed.
