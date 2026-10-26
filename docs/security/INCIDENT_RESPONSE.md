# AgentMesh Incident Response

**Last updated:** 26 October 2026

Runbooks for the incidents AgentMesh is most likely to face. Every operation named here exists in the code and is covered by tests; endpoints are relative to `https://<api>/api/v1`. Staff actions need an operator or admin account with MFA completed.

## 0. First steps for any incident

1. Open a private incident note: time, who is involved, what was observed.
2. Preserve evidence before changing anything: export the relevant audit log (`GET /admin/audit-logs`), application logs from the hosting platform, and `GET /admin/reconciliation`.
3. Contain (sections below), then fix, then recover.
4. Decide on user notification (section 7).

## 1. Compromised or misbehaving provider node

Signs: anomaly report flags (`GET /admin/anomalies`), customer complaints about wrong output, unexpected traffic, a provider reporting a stolen machine.

1. **Contain at once:** `POST /admin/nodes/{id}/quarantine` with `{"reason": "..."}`.
   - The node can no longer authenticate.
   - All its node sessions end and its tunnel closes immediately.
   - Its deployments move to other nodes or fail.
   - The action is audited (`node.quarantined`).
   - The worker keeps its credential and retries every minute.
2. Investigate using the audit log, usage records for the node, charges and the anomaly report. No prompts are stored, so evidence is metadata only.
3. Then either:
   - **release**: `POST /admin/nodes/{id}/release` (audited); the node returns OFFLINE and goes ONLINE at its next authenticated heartbeat; or
   - **revoke permanently**: `POST /nodes/{id}/revoke`. The credential is deleted and sessions end; the worker stops its workloads and deletes its credentials.
4. Refund affected customers for charges served by the node: `POST /admin/refunds/charges/{id}`. The provider's share and the commission are reversed proportionally.

**Revocation latency.** HTTP calls are checked on every request, so cut-off is immediate. Open tunnels re-check every `TUNNEL_REVALIDATE_SECONDS` (default 15 s, maximum 30 s). Long polls re-check before leasing work. A revoked node therefore loses access within 15 seconds even if the disconnect message between replicas is lost (`server/tests/test_node_security.py`).

## 2. Leaked credentials

| What leaked | Action |
|---|---|
| A customer API key | Customer or staff: `DELETE /api-keys/{id}`. Takes effect on the next request. |
| A user's password or session | User: `POST /auth/logout-all`. Staff: set the account inactive, which ends every session on the next request. Ask the user to change their password with the operator's help (there is no self-service reset yet). |
| A refresh token | Its first reuse ends the session automatically (`auth.session_revoked`, reason `refresh_token_reuse`). |
| A node enrollment credential | Revoke the node (§1). With `ALLOW_LEGACY_NODE_CREDENTIALS=false`, the credential alone cannot authenticate (it also needs the node's private key). |
| `PAYSTACK_SECRET_KEY` | Roll the key in the Paystack dashboard, update the platform secret, redeploy. Run reconciliation. |
| `METRICS_TOKEN`, `AI_INFERENCE_TOKEN` | Replace the platform secret and redeploy (update the inference adapter too). |
| `SECRET_KEY` | See §3. |
| A secret committed to git | Treat as leaked whatever happens next: **rotate first.** Removing it from history afterwards does not make it safe. |

## 3. Key rotation

Generate keys with `openssl rand -hex 32` (SECRET_KEY) or `openssl rand -base64 32` (32-byte keys). Set them only in the hosting platform's secret store.

- **`SECRET_KEY`.** Every purpose key is derived from it (`server/app/core/keys.py`): access tokens, MFA challenges, sponsored-view tokens, and (unless set explicitly) command signing and MFA-secret encryption. Rotating it:
  - signs everyone out;
  - makes MFA seeds unreadable if `DATA_ENCRYPTION_KEY` is unset (staff must re-enrol);
  - changes the command-signing key, which workers will refuse unless it is endorsed.

  So before rotating, set `COMMAND_SIGNING_KEY` to the **current** signing seed and `DATA_ENCRYPTION_KEY` to a dedicated key. Re-encrypting existing seeds under a new key is not automated: staff re-enrol MFA after a `DATA_ENCRYPTION_KEY` change unless the old key stays available.
- **Command signing key (overlap window).**
  1. Copy the current `COMMAND_SIGNING_KEY` into `COMMAND_SIGNING_PREVIOUS_KEY`.
  2. Set a new `COMMAND_SIGNING_KEY` and deploy.
  3. Each worker receives the new key with an endorsement signed by the old key at its next heartbeat or session renewal (within about 15 seconds and 1 hour respectively), and pins it.
  4. Keep the previous key configured for at least 2 hours (two session lifetimes) and until every active worker has heartbeated, then remove it.

  If the signing key itself is compromised, endorsement must not be used (the attacker could endorse their own key). Instead re-enroll workers: revoke nodes and ask providers to enroll again, which pins the new key.
- **Worker release signing key** (offline). Workers trust only the key pinned in their own configuration (`AGENTMESH_UPDATE_PUBLIC_KEY`, written by the installer), and there is no in-band rotation.
  1. Generate a new key with `server/scripts/sign_worker_release.py keygen`.
  2. Publish the new public key in the provider docs.
  3. Providers update `AGENTMESH_UPDATE_PUBLIC_KEY` (or re-run the installer) and restart the worker.
  4. Until a worker's config is updated, it refuses new releases; it keeps running its current version.

  If the old key is compromised, announce it so providers stop trusting it.
- **Paystack, metrics and AI tokens.** Replace and redeploy (§2).

## 4. Defective or compromised release (rollback)

- **Control plane.**
  1. Roll back on the hosting platform to the previous good deploy (Render's deploy history) or revert the commit on `main`. Every change is a single reviewed commit.
  2. Database changes are additive; no migration needs reversing.
  3. Run `POST /admin/reconciliation/run`.
- **Dashboard.** Promote the previous Vercel deployment.
- **Worker release.** Workers only accept signed releases. To stop a bad version spreading:
  1. Remove the release from `WORKER_RELEASE_DIR` / GitHub Releases.
  2. Publish a fixed version with a higher number. Workers auto-update only when idle and roll back to the previous wheel if the new one fails its health check.
  3. If the release was **malicious** (signing key compromised), rotate the release key (§3) and quarantine nodes that ran it.
- **Compromised CI or dependency.**
  1. Revoke GitHub tokens and secrets.
  2. Review the commits and actions involved; all actions are SHA-pinned, so check which SHA ran.
  3. Rebuild from a known-good commit.
  4. Compare attestations (`gh attestation verify`) for released assets.

## 5. Service recovery

1. Check health: `GET /health` (process) and `GET /health/ready` (database and Redis).
2. Database loss: restore with `server/ops/restore_db.sh` from the newest archive or the provider's snapshot, then run the retention job, then reconciliation.
3. After restore, workers re-authenticate (sessions and signed commands are re-established automatically). Deployments whose state is behind are reconciled by heartbeats.
4. Payments: reconciliation checks unresolved top-ups, payouts and refunds against Paystack every 10 minutes when payments are enabled.

## 6. Account takeover of a staff account

1. Disable the account (set it inactive in the database, or with another admin). This ends all sessions.
2. Review its audit trail: payouts approved, refunds, pricing or commission changes, node revocations, sponsorship edits.
3. Reverse harmful financial actions with new ledger entries (refunds, adjustments), never by editing records.
4. Re-enable only after a password change and MFA re-enrolment (clear `mfa_secret` so the user sets up a new authenticator).

## 7. User notification

- Notify affected users without undue delay once an incident affecting their personal data is confirmed. Include what happened, which data, what we did, and what they should do (revoke keys, sign out everywhere, watch payments).
- Where the Nigeria Data Protection Act 2023 applies, notify the Nigeria Data Protection Commission of a personal data breach within **72 hours** of becoming aware of it, and notify data subjects where the breach is likely to put their rights at high risk. Under the EU/UK GDPR the supervisory-authority deadline is also 72 hours.
- Providers affected by a node incident get the quarantine reason and the investigation outcome.
- Contact for incident communications: meshachzakumi@gmail.com.
