# AgentMesh Security Implementation Report

**Date:** 26 October 2026
**Branch:** `security-hardening`. It starts from `f0350f1` (business-model work), adds 15 security commits up to `4f678a2`, and is not pushed.
**Scope:** the privacy and security brief, applied to the repository as audited in [`GAP_REPORT.md`](GAP_REPORT.md).

Nothing here was run against production, Render, Vercel, a real provider node or Paystack. Everything ran locally against a private MongoDB replica set started by the test suite.

## 1. Summary

The audit found 1 critical, 8 high and 9 medium issues. All of them are fixed, partly fixed, or explicitly left open below. Main changes:

- **Fail-closed configuration.** An unset `ENVIRONMENT` now means production, so the public default `SECRET_KEY` can no longer be used to forge admin tokens.
- **Deployment exposure.**
  - Compose no longer publishes an unauthenticated Redis.
  - Client addresses are taken from `X-Forwarded-For` only when the request comes from configured proxies.
  - WebSocket messages are capped.
- **Authentication.**
  - Argon2id password hashing, with old hashes upgraded at next login.
  - Login timing no longer reveals which emails exist.
  - 15-minute access tokens bound to revocable server-side sessions, with single-use refresh tokens and reuse detection.
  - Logout and logout-all end sessions on the server.
  - TOTP MFA is required for operators and admins.
  - Every key purpose uses its own HKDF-derived key.
- **Node identity.**
  - Operator quarantine.
  - Revocation reaches open tunnels within 15 s, even if the disconnect message is lost.
  - One-hour node sessions that need the node's private key.
  - Ed25519-signed command authorizations bound to the node, command, payload, expiry and a nonce; workers pin the key and refuse anything else.
- **Privacy.**
  - Retention per data class, enforced hourly.
  - Customers can delete finished AI runs, with a report of what was deleted.
  - Canary tests show prompts, outputs and credentials stay out of the logs.
- **Billing integrity.**
  - Provider-reported input tokens are now bounded, as output tokens already were.
  - A new operator anomaly report.
  - Tests for concurrent billing and for interrupted work.
- **Application.**
  - Dashboard CSP and HSTS.
  - No API docs in production.
  - Hostile-input tests, which found one real defect: deep JSON nesting caused a 500.
- **Supply chain.**
  - SHA-pinned actions and minimal workflow permissions.
  - Scans on every pull request, all failing the build when they find something.
  - Digest-pinned images built from complete lock files.
  - Two vulnerable dependency sets fixed (certifi, and 13 npm advisories).
- **Documentation.** `SECURITY.md`, threat model, permissions, data handling, incident response, and the privacy notice (draft, pending legal review).

## 2. Findings

| ID | Severity | Status | Evidence |
|---|---|---|---|
| G-01 | CRITICAL | FIXED | `server/app/core/config.py` (`ENVIRONMENT = "production"`); `tests/test_config.py::test_unset_environment_fails_closed` |
| G-02 | HIGH | FIXED | `docker-compose.yml` (no Redis port, `--requirepass`); `tests/test_deployment_config.py::test_compose_does_not_expose_redis_or_mongo_and_requires_a_redis_password` |
| G-03 | HIGH | FIXED (code). **Deployment action required** (§8) | `Dockerfile.server` (`FORWARDED_ALLOW_IPS`, `--proxy-headers`), `docker-compose.yml`; `tests/test_deployment_config.py::test_login_throttle_keys_on_the_real_client_address` |
| G-04 | HIGH | FIXED | `server/app/documents/session.py`, `app/core/dependencies.py`, `app/services/auth_service.py`, `client/src/lib/api.ts`; `tests/test_auth_security.py` (session tests), `client/src/lib/__tests__/session.test.ts` |
| G-05 | HIGH | FIXED | `app/services/mfa_service.py`, `app/core/crypto.py`, `app/core/dependencies.py::get_current_user`; `tests/test_auth_security.py` (MFA tests) |
| G-06 | MEDIUM | PARTIAL | Login timing fixed (`burn_password_check`; `test_unknown_email_costs_a_password_check_and_gets_the_same_answer`). Registration still answers "Email already registered". |
| G-07 | MEDIUM | PARTIAL | Argon2id via argon2-cffi 25.1.0 (`app/core/security.py`; `test_passwords_are_hashed_with_argon2id`, `test_legacy_pbkdf2_hash_still_works_and_is_upgraded_at_login`). passlib 1.7.4 is still used to verify pre-existing hashes. |
| G-08 | HIGH | PARTIAL | Node sessions implemented and verified, including with legacy mode off, by the real worker end to end (§5). `ALLOW_LEGACY_NODE_CREDENTIALS` defaults to `true` until workers are upgraded. `tests/test_node_sessions.py` |
| G-09 | HIGH | FIXED | `app/services/node_service.py::quarantine_node`, `/admin/nodes/{id}/quarantine` and `/release`; `tests/test_node_security.py::test_operator_quarantine_cuts_a_node_off_at_once_and_is_reversible` |
| G-10 | MEDIUM | FIXED | `app/api/v1/worker.py::_revalidate`, `worker_service.still_authorized`; `test_revoked_node_loses_its_tunnel_within_the_window_even_if_the_disconnect_is_lost`, `test_a_long_poll_cannot_lease_work_after_revocation` |
| G-11 | MEDIUM | FIXED | `app/core/signing.py`, `node_agent/command_auth.py`, nonce-bound acks; `tests/test_node_sessions.py` (12 authorization tests) |
| G-12 | MEDIUM | FIXED | `app/services/retention_service.py`, `DELETE /ai/deployments/{id}`; `tests/test_privacy.py` (retention and deletion) |
| G-13 | MEDIUM | FIXED | Canary tests in `tests/test_privacy.py`; allowlisted security events in `app/core/security_events.py`. General log redaction is still pattern based. |
| G-14 | MEDIUM | PARTIAL | CSP and HSTS in `client/src/lib/securityHeaders.ts`; `securityHeaders.test.ts`; headers confirmed on a local `next start`. Scripts still allow `'unsafe-inline'`. Not checked in a browser for CSP violations. |
| G-15 | LOW | FIXED | `app/main.py` (docs URLs only when `api_docs_enabled`); `tests/test_input_safety.py::test_production_turns_debug_features_off` |
| G-16 | MEDIUM | PARTIAL | Workflows hardened and policy-tested (`tests/test_ci_policy.py`). **The workflows have not run on GitHub Actions** (branch not pushed). |
| G-17 | MEDIUM | PARTIAL | Digest-pinned bases, complete locks, no compilers (`Dockerfile.*`, `requirements-*lock.txt`; `test_ci_policy.py`). **Images not built locally** (no Docker access); `--only-binary` wheel availability for Python 3.12 not confirmed (see §7). |
| G-18 | MEDIUM | PARTIAL | Real-Docker isolation tests in `tests/test_worker_isolation_docker.py`, **skipped here**. Non-root workloads and per-GPU assignment not implemented. |
| G-19 | LOW | ACCEPTED | The maintainer chose to keep the legacy `POST /nodes/register` (26 October 2026). Its keys now use SHA-256 secret hashes (`test_legacy_node_registration_keys_use_a_fast_secret_hash`). |
| G-20 | LOW | OPEN | `ALLOW_INSECURE_CONTROL_PLANE` is unchanged; documented. Signed commands limit the impact. |
| G-21 | LOW | OPEN | Ollama models are still pulled by tag. |
| G-22 | MEDIUM | PARTIAL | Input-token cap and anomaly report (`app/services/billing_service.py`, `reporting_service.provider_anomalies`; `tests/test_billing_integrity.py`). Honest execution is still unverifiable (THREAT_MODEL A2). |
| G-23 | LOW | FIXED | `--ws-max-size 2097152` in `Dockerfile.server`; `test_compose_and_image_never_trust_forwarded_headers_from_everyone` |
| G-24 | INFO | No action | History scan: no real secrets (§6) |
| G-25 | MEDIUM | FIXED | `RecursionError` handler in `app/main.py`; `test_malformed_and_injection_bodies_get_a_clean_4xx[deeply-nested]` |

## 3. Files changed (98 files, +5,650 / −620 since `f0350f1`)

- **Configuration and deployment:**
  - `.env.example`, `.gitignore`, `docker-compose.yml`
  - `Dockerfile.server`, `Dockerfile.node-agent`, `Dockerfile.client`
  - `server/requirements.txt`, `server/requirements-lock.txt`, `server/requirements-worker-lock.txt` (new)
- **CI:**
  - `.github/workflows/ci.yml`, `security.yml`, `worker-release.yml`
  - `.github/dependabot.yml`
- **Core:**
  - `server/app/main.py`
  - `app/core/config.py`, `security.py`, `dependencies.py`
  - new: `keys.py`, `crypto.py`, `signing.py`, `security_events.py`
- **Auth:**
  - `app/api/v1/auth.py`, `app/schemas/auth.py`, `app/services/auth_service.py`
  - new: `app/services/mfa_service.py`, `app/documents/session.py`
  - `app/documents/user.py`
- **Nodes and worker protocol:**
  - `app/api/v1/worker.py`, `app/api/v1/admin.py`, `app/schemas/worker.py`, `app/schemas/node.py`
  - `app/services/worker_service.py`, `node_service.py`, `placement_service.py`
  - `app/documents/node.py`, `worker.py`, new `node_session.py`
- **Worker agent:**
  - new `server/node_agent/command_auth.py`
  - `protocol.py`, `identity.py`, `tunnel.py`, `worker.py`, `runtime/ollama_docker.py`, `runtime/vllm.py`
- **Privacy and billing:**
  - new `app/services/retention_service.py`
  - `app/background/monitors.py`, `app/api/v1/ai.py`, `app/api/v1/gateway.py`
  - `app/documents/usage.py`, `app/services/billing_service.py`, `reporting_service.py`, `sponsorship_service.py`
- **Dashboard:**
  - `client/next.config.ts`, new `src/lib/securityHeaders.ts`
  - `src/lib/api.ts`, `src/lib/auth.ts`, `src/stores/authStore.ts`, `src/hooks/useAuth.ts`, `src/types/user.ts`
  - `src/components/auth/LoginForm.tsx`, `AuthGuard.tsx`, new `MfaSetup.tsx`, new `src/app/mfa-setup/page.tsx`
  - `package-lock.json`
  - docs pages: `security`, `api`, `operators`, `providers`; `src/lib/docs.ts`
- **Tests (server):**
  - new: `test_route_guards.py`, `test_tenant_isolation.py`, `test_auth_security.py`, `test_node_security.py`, `test_node_sessions.py`, `test_privacy.py`, `test_input_safety.py`, `test_billing_integrity.py`, `test_ci_policy.py`, `test_deployment_config.py`, `test_worker_isolation_docker.py`, `mfa_support.py`
  - updated: `conftest.py`, `test_config.py`, `test_dashboards.py`, `test_node_agent/test_worker.py`, `test_node_agent/test_phase4.py`
- **Tests (client):**
  - new: `session.test.ts`, `securityHeaders.test.ts`, `MfaSetup.test.tsx`
  - updated: `authStore.test.ts`
- **Documentation:**
  - `SECURITY.md`
  - `docs/security/` `GAP_REPORT.md`, `THREAT_MODEL.md`, `PERMISSIONS.md`, `DATA_HANDLING.md`, `INCIDENT_RESPONSE.md`, `IMPLEMENTATION_REPORT.md`
  - `docs/PRIVACY_NOTICE.md`

## 4. Controls and the tests that verify them (brief §11)

| # | Requirement | Test(s) | Result |
|---|---|---|---|
| 1 | Unauthenticated requests to every protected route rejected | `test_route_guards.py`: static check of every route, plus 210 anonymous/forged-token requests, plus the tunnel handshake | PASS |
| 2 | Client A cannot touch client B's resources | `test_tenant_isolation.py` (5), `test_authorization.py` | PASS |
| 3 | Provider cannot fetch jobs not authorized for its node | `test_tenant_isolation.py::test_provider_cannot_manage_or_impersonate_another_providers_node`, `test_node_sessions.py::test_authorization_for_another_node_is_refused` | PASS |
| 4 | Expired, malformed, revoked credentials rejected | `test_auth_security.py::test_malformed_expired_and_foreign_tokens_are_rejected`, `test_node_security.py::test_wrong_or_missing_node_credentials_are_rejected`, `test_node_sessions.py::test_expired_challenge_and_expired_session_are_refused` | PASS |
| 5 | Modified, expired, replayed, misbound, badly signed authorizations rejected | `test_node_sessions.py` (tampered, misbound, other node, expired, unknown key, replay, endorsed rotation, stale-nonce ack) | PASS |
| 6 | Duplicate and concurrent completion yields one charge | `test_billing_integrity.py::test_concurrent_and_repeated_billing_runs_produce_exactly_one_charge`, `test_duplicate_metering_of_one_request_is_counted_once`, `test_billing.py::test_ledger_postings_are_idempotent` | PASS |
| 7 | Interrupted, timed-out, failed work never successful | `test_billing_integrity.py::test_failed_cancelled_and_timed_out_requests_are_never_billed`, `test_interrupted_deployments_are_never_revived_by_a_worker` | PASS |
| 8 | Workers cannot reach the Docker socket, host filesystem or metadata | `test_worker_isolation_docker.py` (socket/host paths, metadata) | **SKIPPED (no Docker daemon access). Unverified.** |
| 9 | CPU, memory, PID, timeout limits enforced | `test_worker_isolation_docker.py` (memory, PIDs); wall-clock timeouts covered by `test_gateway.py::test_first_byte_timeout` | Memory/PID **SKIPPED, unverified**; timeouts PASS. CPU throttling not tested. |
| 10 | No route to internal ranges | `test_worker_isolation_docker.py` (169.254.169.254, 10/8, 192.168/16, 172.16/12, internet) | **SKIPPED, unverified** |
| 11 | Prompts, outputs and credentials absent from logs | `test_privacy.py` canary tests (5) | PASS |
| 12 | Retention deletes expired data; client deletion works and is authorized | `test_privacy.py::test_retention_purges_each_data_class_after_its_period`, `test_customer_deletes_a_finished_ai_run_and_is_told_what_went` | PASS |
| 13 | Revoked nodes cut off within the window | `test_node_security.py::test_revoked_node_loses_its_tunnel_within_the_window_even_if_the_disconnect_is_lost` (1 s window in test; 15 s default, 30 s max) | PASS |
| 14 | Oversized, malformed, malicious input rejected safely | `test_input_safety.py` (size, nesting, control bytes, operator injection, generic 500) | PASS |
| 15 | Reconnection re-runs full authentication | `test_node_security.py::test_reconnection_after_an_outage_is_fully_reauthenticated`, quarantine reconnect check | PASS |
| 16 | Mass assignment and role escalation fail | `test_input_safety.py` mass-assignment tests, `test_authorization.py::test_privileged_roles_cannot_self_register` | PASS |
| 17 | SSRF blocked, including redirects | `test_input_safety.py` (model-import hosts, no redirects), `test_node_agent/test_model_store.py::test_redirect_to_disallowed_host_is_refused` | PASS |
| 18 | Production config: debug off, CORS restricted | `test_input_safety.py::test_production_turns_debug_features_off`, `test_running_app_has_debug_off_and_no_wildcard_cors`, `test_cors_answers_only_listed_origins` | PASS |

Other controls with tests:
- staff MFA enforcement and enrolment: `test_auth_security.py`;
- refresh rotation and reuse detection: `test_refresh_rotates_and_reuse_revokes_the_whole_session`;
- Argon2id: `test_passwords_are_hashed_with_argon2id`;
- encrypted MFA seeds bound to context: `test_encrypted_values_are_bound_to_their_context_and_key`;
- quarantine: `test_node_security.py`;
- CSP: `securityHeaders.test.ts`;
- supply-chain policy: `test_ci_policy.py`;
- token-claim caps and anomaly report: `test_billing_integrity.py`.

## 5. Test results

All commands were run on 26 October 2026 on the development machine (Python 3.14.4, Node v22.22.1, npm 9.2.0). The output below is trimmed, not edited.

```
$ cd server && python -m pytest tests/ -q -p no:warnings -rs
SKIPPED [1] tests/test_ai_adapter.py:318: set AGENTMESH_TEST_OLLAMA_URL and _MODEL to run
SKIPPED [1] tests/test_worker_isolation_docker.py:62: Docker daemon not reachable: DockerException
SKIPPED [1] tests/test_worker_isolation_docker.py:67: Docker daemon not reachable: DockerException
SKIPPED [1] tests/test_worker_isolation_docker.py:73: Docker daemon not reachable: DockerException
SKIPPED [5] tests/test_worker_isolation_docker.py:78: Docker daemon not reachable: DockerException
SKIPPED [1] tests/test_worker_isolation_docker.py:84: Docker daemon not reachable: DockerException
SKIPPED [1] tests/test_worker_isolation_docker.py:89: Docker daemon not reachable: DockerException
================= 754 passed, 11 skipped in 185.35s (0:03:05) ==================

$ ruff check .            ->  All checks passed!
$ ruff format --check .   ->  206 files already formatted
$ mypy app                ->  Success: no issues found in 116 source files

$ cd client && npx tsc --noEmit                ->  (no output, exit 0)
$ npx eslint src next.config.ts                ->  (no output, exit 0)
$ npx jest                                     ->  Test Suites: 12 passed, 12 total / Tests: 70 passed, 70 total
$ npx next build                               ->  ✓ Compiled successfully
```

**Skipped tests (11), none counted as passing:**
- `test_worker_isolation_docker.py`, 10 tests: this user cannot reach `/var/run/docker.sock` ("permission denied"). CI sets `AGENTMESH_ISOLATION_PULL=1` and runs them on GitHub's Docker-enabled runners. That run has not happened yet.
- `test_ai_adapter.py:318`, 1 test (existing): needs a real Ollama URL. The user's Ollama service was deliberately not used.

**End-to-end run of the real worker** against a locally started control plane with `ALLOW_LEGACY_NODE_CREDENTIALS=false`, using the stub runtime `tests/fixtures/fake_ollama.py`:

```
$ python scripts/e2e_ollama.py --api http://127.0.0.1:<port> --mode agent --model smollm2:135m --ollama-binary tests/fixtures/fake_ollama.py
[PASS] worker enrolled with one-time token ... [PASS] deployment READY after verified test generation ...
[PASS] other customer cannot reach deployment ... [PASS] worker shut down gracefully - exit code 0
All 22 checks passed.
worker.log: "Node session established (valid 3600s)"
```

This shows the real worker obtaining a session with its key and executing only signed commands. Model inference itself was stubbed.

## 6. Scanner results

| Tool (version) | Target | Findings | Disposition |
|---|---|---|---|
| pip-audit 2.9.0 | `server/requirements-lock.txt` | Before: 1 (`certifi 2026.7.22`, PYSEC-2026-4320). After: "No known vulnerabilities found" | Fixed: certifi → 2026.10.19 |
| pip-audit 2.9.0 | `server/requirements-worker-lock.txt` | "No known vulnerabilities found" | — |
| npm audit (npm 9.2.0) | `client/` | Before: 13 (9 high, 4 moderate; including `follow-redirects`, used by axios at runtime, plus `undici`, `zod`, `brace-expansion`, `qs`). After: "found 0 vulnerabilities" | Fixed: `npm audit fix` (lockfile only, no major upgrades); tsc, eslint, jest and build re-run green |
| Bandit 1.9.4 (`-ll`) | `server/app`, `node_agent`, `ai_adapter` | 0 medium/high after review; 27 low (not gated); 4 suppressed per line | 4 reviewed false positives, each with the reason on the line above: SHA-1 inside RFC 6238 TOTP, two container-internal `/tmp` tmpfs mounts, vLLM's `0.0.0.0` inside its internal-network container. Bandit 1.8.6 crashed on Python 3.14 (`'Constant' object has no attribute 's'`), so 1.9.4 is pinned. |
| Custom history scan (pattern search over every blob, values never printed) | Full git history, 1,033 objects | 27 hits, all placeholders, variable references or test fixtures (e.g. `user:pass@cluster0.example`, `${REDIS_PASSWORD}`, a 5-character fake Paystack key) | No real secrets; nothing to rotate |
| gitleaks 8.24.3 | Full history | **NOT RUN locally** (binary download not allowed on this machine without approval) | Runs in CI, checksum-verified |
| Trivy v0.36.0 action (image, config, SBOM) | Images, Dockerfiles, compose, workflows | **NOT RUN** (no Docker access locally; CI not yet executed) | Gate configured with `exit-code: 1` |
| actionlint | Workflows | **NOT RUN** (binary) | YAML structure and policy checked by `test_ci_policy.py` |

## 7. Unresolved vulnerabilities and incomplete requirements (by severity)

1. **HIGH, until upgraded:** legacy node credentials are still accepted (`ALLOW_LEGACY_NODE_CREDENTIALS=true`), so a stolen enrollment credential works on its own until it is turned off. It needs a worker release containing this code, rolled out to providers. `WORKER_VERSION` is still `0.3.0` and has not been bumped or released.
2. **MEDIUM:** worker isolation (G-18) is unverified here, and workloads run as the image's default user (root for `ollama/ollama`). GPU deployments see all GPUs, the model cache volume is shared between deployments, and process-mode runtimes have no sandbox.
3. **MEDIUM:** CI hardening and images (G-16, G-17) are configured but **not executed**: workflows have not run, images were not built, and Trivy and gitleaks results are unknown. If any pinned package lacks a cp312 wheel, the `--only-binary` image build will fail and need adjusting.
4. **MEDIUM:** the CSP allows `'unsafe-inline'` scripts and has not been checked in a browser. Tokens stay in `localStorage` (THREAT_MODEL A4).
5. **MEDIUM:** provider honesty is unverifiable (A2). Token caps bound inflation; they do not prove the model ran.
6. **LOW:** registration reveals existing emails (G-06). passlib (unmaintained) is kept for verifying legacy hashes (G-07). `ALLOW_INSECURE_CONTROL_PLANE` is unchanged (G-20). Ollama models are pulled by tag (G-21). The legacy `/nodes/register` is kept by decision (G-19).
7. **Incomplete requirements:**
   - no self-service account deletion or password reset;
   - application-log retention depends on the hosting plan;
   - Render, MongoDB Atlas and Vercel settings (encryption at rest, backups, served headers) were not inspected;
   - the audit log is not tamper-evident;
   - there is no provider agreement or acceptance flow in the product, yet the privacy notice's §6 describes provider rules.

## 8. Deployment changes and required environment variables

**Effects of deploying this branch:**
- **Everyone is signed out once.** The access-token format changed and old tokens have no session.
- **Operators and admins must set up an authenticator app** at their next sign-in (`/mfa-setup`) before staff features work.
- New MongoDB collections and indexes (`auth_sessions`, `refresh_tokens`, `node_sessions`, `node_challenges`) are created automatically at startup. No destructive migration.
- Workers already running keep working (legacy mode). Upgraded workers use sessions and verify signatures; they pin the signing key at their next heartbeat.

**Environment variables** (names only; set values in the platform's secret store):

| Variable | Required? | Notes |
|---|---|---|
| `ENVIRONMENT` | Set explicitly | Unset now means production. Development and test environments must set `development` or `test`. |
| `SECRET_KEY` | Yes (existing) | Root of the derived purpose keys. Read the rotation notes in INCIDENT_RESPONSE.md §3 first. |
| `FORWARDED_ALLOW_IPS` | **Yes on Render** if the API runs from `Dockerfile.server` | Render's proxy addresses (to be confirmed with Render). Otherwise all clients share one rate-limit bucket. Compose requires it. |
| `REDIS_PASSWORD` | Compose only | Required by `docker-compose.yml`. With external Redis, put the password in `REDIS_URL`. |
| `STAFF_MFA_REQUIRED` | Optional (default `true`) | |
| `DATA_ENCRYPTION_KEY` | Recommended | `openssl rand -base64 32`. Dedicated key for MFA seeds; without it they are encrypted with a key derived from `SECRET_KEY`. |
| `COMMAND_SIGNING_KEY` | Recommended | `openssl rand -base64 32`. Decouples command signing from `SECRET_KEY`. **Set it before the first upgraded worker pins a key,** or later rotate with `COMMAND_SIGNING_PREVIOUS_KEY`. |
| `COMMAND_SIGNING_PREVIOUS_KEY` | During rotation only | |
| `ALLOW_LEGACY_NODE_CREDENTIALS` | Default `true` | Set `false` once every worker runs the new version. |
| `NODE_SESSION_TTL_MINUTES`, `TUNNEL_REVALIDATE_SECONDS`, `COMMAND_AUTH_TTL_SECONDS` | Optional | Defaults 60, 15, 600. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_TTL_DAYS` | Optional | Defaults 15 (maximum 15), 14. |
| `AI_INFERENCE_RESULT_RETENTION_HOURS`, `AI_RUN_RETENTION_DAYS`, `USAGE_RECORD_RETENTION_DAYS`, `DEPLOYMENT_EVENT_RETENTION_DAYS`, `AUDIT_LOG_RETENTION_DAYS` | Optional | Defaults 24, 90, 400, 180, 365. |
| `API_DOCS_ENABLED` | Optional (default `false`) | Re-enables Swagger in production. |

**New dependency:** `argon2-cffi==25.1.0` (with `argon2-cffi-bindings==26.1.0`). Images now install from the lock files.
