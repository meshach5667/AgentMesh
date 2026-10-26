# AgentMesh Security Gap Report

**Audit date:** 26 October 2026
**Scope:** the repository at commit `3ff2d0f` (branch `mongodb-migration`) plus the uncommitted business-model work (Phases 1 to 3: commission, refunds, analytics, sponsorships).
**Method:** I read the code and configuration directly and searched the full git history for secrets. Nothing was taken on trust from comments or docs. No production system, deployed service or real provider node was contacted.

## 1. What was inspected

| Area | What exists (verified in code) |
|---|---|
| Layout | `server/` (FastAPI control plane `app/`, provider worker `node_agent/`, AI inference adapter `ai_adapter/`), `client/` (Next.js 16 dashboard), Dockerfiles, two compose files, three GitHub workflows |
| Database | MongoDB replica set via Beanie/pymongo, with a custom unit-of-work `Session` (`server/app/core/mongo.py`). There are no migrations; indexes are created at startup |
| Auth | Email and password, hashed with passlib `pbkdf2_sha256` (`server/app/core/security.py:13`). The access token is an HS256 JWT signed with `SECRET_KEY`, valid 60 min (`server/app/core/config.py:25`), with no refresh and no server-side revocation. Roles: customer, provider, operator, admin, enforced through `require_roles` (`server/app/core/dependencies.py:41`) |
| API keys | Hashed with SHA-256, shown once, scoped, optionally bound to a deployment, revocable (`server/app/services/api_key_service.py`) |
| Node agent | Enrolls with a one-time token (60 min TTL, atomic claim at `server/app/services/worker_service.py:92`) and receives a long-lived bearer credential `am_node_…` (`worker_service.py:106`). Talks outbound over HTTPS polling plus a WebSocket tunnel for inference (`server/app/api/v1/worker.py:124`). It has an RSA keypair (`server/node_agent/identity.py`), but "protocol v1 authenticates with the node credential only" (`identity.py:2`) |
| Model runtimes | Ollama, llama.cpp, vLLM, as processes bound to `127.0.0.1` (`node_agent/runtime/ollama_process.py:65`) or Docker containers published on loopback or an `internal` network (`node_agent/runtime/ollama_docker.py:143-146`) |
| Workloads | AgentMesh runs long-lived **deployments**, not one-shot jobs. A customer deploys a model onto a node; inference requests are proxied through the node's tunnel (`server/app/api/v1/gateway.py`). Commands (`DEPLOY`, `STOP`, `RESTART`) are leased from a persisted queue (`server/app/documents/worker.py:47`) |
| Billing | Rated charges are unique per (deployment, node, period) (`server/app/documents/billing.py:74`). Usage records are unique per gateway request id. The ledger is append-only with idempotency keys |
| URL fetching | Hugging Face metadata: fixed host, no redirects, size cap (`server/app/services/huggingface.py:1-7`). The worker downloads GGUF files over https from allowlisted hosts on every redirect hop, verified by SHA-256 (`node_agent/runtime/model_store.py:1-11`) |
| Tool calling | The AI deployment agent has a fixed allowlist of tools scoped to the caller's own deployments (`server/app/services/ai/tools.py`). There is no arbitrary code or shell execution |
| Tests | pytest: 435 passed, 1 skipped, against a local MongoDB replica set. Jest: 57 passed |
| CI | `ci.yml` (lint, tests, image build, e2e with a stub runtime), `security.yml` (pip-audit, npm audit, gitleaks, Trivy), `worker-release.yml` |

## 2. Findings

Status of each finding after implementation: [`IMPLEMENTATION_REPORT.md`](IMPLEMENTATION_REPORT.md).

Severity follows the brief: CRITICAL means remote compromise, cross-tenant access or secret exposure.

| ID | Severity | Component | Evidence (file:line) | Description | Exploit scenario | Proposed fix |
|---|---|---|---|---|---|---|
| G-01 | CRITICAL | Config | `server/app/core/config.py:24`, `:28`, `:33`, `:162-163`, `:190-203` | `ENVIRONMENT` defaults to `dev`. In dev, the production safety checks are skipped, so the server starts with `SECRET_KEY="supersecretkey"`, and unpaid test credits are allowed (fail-open). | A deployment that forgets `ENVIRONMENT` signs JWTs with a public key. Anyone can mint an admin token (`{"sub": <admin uuid>}`) and take over the platform. | Fail closed: default to `production`, so dev and test must opt in explicitly. Refuse to start in non-dev mode with weak secrets. |
| G-02 | HIGH | Deployment (compose) | `docker-compose.yml:24` | Redis is published on host port 6379 with no password. Replicas trust Redis pub/sub messages for tunnel routing (`server/app/services/tunnel.py:176-233`) and use Redis for rate limits. | Anyone who can reach the host injects `frame` messages (forged inference responses to customers), `close_node` messages (disconnects nodes), or deletes rate-limit keys. | Do not publish Redis. Require a password through `REDIS_URL`. |
| G-03 | HIGH | Deployment / auth | `docker-compose.yml:58`, `Dockerfile.server:23`, `server/app/api/v1/auth.py:15` | Compose trusts `X-Forwarded-For` from any source (`--forwarded-allow-ips='*'`) while also publishing port 8000 directly. The image's default command trusts only `127.0.0.1`, so behind a hosting proxy every client appears as the proxy's address. | Compose: spoofed `X-Forwarded-For` bypasses per-IP login throttling and the Paystack webhook IP allowlist, and forges audit IPs. Image on a PaaS: one attacker exhausts the shared per-IP login bucket and locks every user out. | Add a `FORWARDED_ALLOW_IPS` setting used by the image and compose (default `127.0.0.1`). Document the value per platform. |
| G-04 | HIGH | Auth | `server/app/core/config.py:25`, `server/app/core/security.py:57-63`, `client/src/lib/auth.ts:12` | Access tokens last 60 minutes and cannot be revoked. There is no refresh rotation, no session record, and no token type or audience claim. Logout only clears browser storage. The token is kept in `localStorage`. | A token stolen through XSS, a shared machine or logs stays valid for up to an hour after logout, disabling or a password change. | Access tokens of 15 minutes or less, bound to a server-side session. Rotating refresh tokens with reuse detection that revokes the family. Logout revokes the session. Add `typ`/`aud` claims. |
| G-05 | HIGH | Auth | (absent) | There is no MFA for operator or admin accounts. | A phished or reused operator password gives full control over payouts, refunds, pricing and node revocation. | TOTP MFA for staff, using `cryptography`'s TOTP (already a dependency). Required by configuration before staff routes can be used. |
| G-06 | MEDIUM | Auth | `server/app/services/auth_service.py:38`, `:12` | Login skips password hashing when the email is unknown, so timing reveals which emails are registered. Registration answers "Email already registered". | Account enumeration for credential stuffing or phishing. | Hash against a dummy value on unknown emails. Registration disclosure is inherent to self-service sign-up; it is rate-limited and documented. |
| G-07 | MEDIUM | Auth | `server/app/core/security.py:13`, `server/requirements.txt:11` | Passwords use PBKDF2-SHA256 through passlib 1.7.4 (unmaintained since 2020; its bcrypt backend is incompatible with the installed bcrypt 5.0.0). | No direct exploit, but it falls short of the Argon2id/bcrypt requirement and depends on an unmaintained library. | Argon2id via `argon2-cffi` (maintained, pinned), rehashing on login. Removing passlib entirely is listed for follow-up. |
| G-08 | HIGH | Node identity | `server/app/services/worker_service.py:106`, `:157-177`, `server/node_agent/identity.py:2` | The node credential is a bearer secret that never expires. The node's public key is stored but never used to authenticate. There is no renewal flow. | A stolen node credential (backup, log or disk image) can impersonate the node indefinitely until someone notices and revokes it. | Short-lived node session tokens (1 h), issued only after the node signs a fresh server challenge with its private key (proof of possession). The enrollment credential alone no longer gets work once legacy mode is off. |
| G-09 | HIGH | Node lifecycle | `server/app/documents/node.py:21`, `server/app/services/worker_service.py:175` | The `SUSPENDED` state exists, but no code sets it: there is no quarantine operation. A suspended node's open tunnel would not be closed. | An operator who sees a misbehaving node can only revoke it permanently. There is no immediate, reversible containment. | Admin quarantine and release endpoints that stop scheduling, close the tunnel and stop serving at once, with audit records. |
| G-10 | MEDIUM | Node revocation | `server/app/api/v1/worker.py:124-148`, `server/app/services/tunnel.py:112-122` | The tunnel is authenticated once, at connect. Revocation relies on a single best-effort `close_node` (a Redis publish when the tunnel is on another replica). There is no periodic recheck, so revocation latency is unbounded if that message is lost. | A revoked node keeps receiving customer prompts over an already-open tunnel. | The tunnel rechecks node status and credential every 15 s and closes if either fails. The gateway refuses nodes that are not active. Documented maximum latency: 30 s. |
| G-11 | MEDIUM | Job authorization | `server/app/services/worker_service.py:239-280`, `server/app/documents/worker.py:47` | Commands reach workers unsigned, with no expiry or nonce. The worker trusts any command arriving over TLS from the configured URL. | Anyone who can answer as the control plane (DNS or TLS compromise, misconfigured `ALLOW_INSECURE_CONTROL_PLANE`, malicious proxy) can make nodes deploy arbitrary models. A captured command can be replayed. | Ed25519-signed command authorizations with key id, node id, command and deployment ids, model and digest, resource limits, `iat`/`exp` and nonce. Workers verify against a pinned public key. The control plane records nonces. |
| G-12 | MEDIUM | Privacy / retention | `server/app/documents/ai.py:26`, `:93`, `:100` | AI agent runs store the customer's request text, and AI inference requests store prompts and model output, indefinitely. Audit logs, usage records and deployment events never expire. Customers cannot delete stored AI runs. | Stored prompt and output content grows without limit and is exposed by any database leak. Customers cannot exercise deletion. | Configurable retention per data class, enforced by a scheduled purge (tested). Authenticated customer deletion of AI runs that reports what was deleted. |
| G-13 | MEDIUM | Logging | `server/app/core/logging.py:19-24` | Redaction is a denylist of secret formats, and no test proves prompts or outputs stay out of logs on error paths. | A future `logger.exception` in the gateway could write prompts or outputs to logs, unnoticed. | Canary tests that push marker strings through the gateway, AI and worker paths, including errors, and assert they appear in no log record. |
| G-14 | MEDIUM | Web client | `client/next.config.ts:3-8` | The dashboard sends no Content-Security-Policy, no HSTS and no `frame-ancestors`. | XSS impact is not contained, which matters more because the token is in `localStorage` (G-04). | Add a CSP (`default-src 'self'`, `connect-src` limited to the API, `frame-ancestors 'none'`, `object-src 'none'`) and HSTS. |
| G-15 | LOW | API | `server/app/main.py:70-73` | OpenAPI and Swagger UI are served in production. | Makes reconnaissance of admin and worker routes easier (they are still authenticated). | Disable the docs URLs outside dev unless explicitly enabled. |
| G-16 | MEDIUM | CI/CD | `.github/workflows/security.yml:60`, `:64`, `:47`, `:32`; `.github/workflows/ci.yml:14` | Actions are pinned by tag, not commit SHA. `trivy-action@master` runs mutable code. Trivy uses `exit-code: '0'`, so it never fails. Security scans do not run on pull requests. No `permissions:` block in `ci.yml` or `security.yml`. gitleaks is downloaded without checksum verification. npm audit fails only on critical. There is no SAST. Dependabot does not cover actions or Docker. | A compromised action tag or Trivy release runs in CI with the default token. Vulnerable images ship silently. | Pin every action to a full SHA, minimal permissions, run scans on PRs, make Trivy fail on fixable HIGH/CRITICAL, verify gitleaks' checksum, add Bandit SAST, extend Dependabot. |
| G-17 | MEDIUM | Images | `Dockerfile.server:1`, `:10-11`; `Dockerfile.node-agent:4`; `Dockerfile.client:2`, `:13` | Base images are pinned by tag, not digest. The server image installs unpinned `requirements.txt` (`>=` ranges) while `requirements-lock.txt` goes unused, and it keeps `build-essential` in the runtime image. | Builds are not reproducible. A malicious or broken release of any dependency ships on the next build. | Install from the lock file and drop build tools from the runtime image. Digest pinning is listed (resolving digests needs registry access, which was not used during this audit). |
| G-18 | MEDIUM | Worker isolation | `server/node_agent/runtime/ollama_docker.py:142`, `:185-193`, `:11-12`; `ollama_process.py:65` | Workload containers run as the image's default user (root for `ollama/ollama`). GPU deployments get every GPU (`count=-1`). The model cache volume is shared read-write across deployments. In loopback mode egress is not restricted. Process-mode runtimes have no sandbox beyond the worker's OS user. | Exploiting a runtime bug (e.g. a malformed model file) gives root in the container and can tamper with other deployments' cached models. | Run workloads as a non-root UID, attach only the assigned GPU, and keep documenting the process mode as unsandboxed. These need a Docker daemon to verify, which this environment does not allow (see §4). |
| G-19 | LOW | Legacy API | `server/app/api/v1/nodes.py:12`, `:58`; `server/app/services/node_service.py:16-27` | The legacy `POST /nodes/register` and deprecated `POST /nodes/{id}/heartbeat` remain enabled. They create nodes without an enrollment token, with passlib-hashed keys. | A second, weaker node-provisioning path that bypasses the enrollment and protocol checks. | Disable both behind a default-off setting. This changes a public endpoint, so I need your decision first (Rule 7). |
| G-20 | LOW | Node agent | `server/node_agent/config.py:90` | `ALLOW_INSECURE_CONTROL_PLANE=true` allows plain HTTP to non-local hosts. | A provider who sets it on a public network leaks the node credential and every prompt. | Keep it as an explicit opt-in, warn loudly in logs, and document it. Signed commands (G-11) limit the damage. |
| G-21 | LOW | Model artifacts | `server/node_agent/runtime/ollama_docker.py:201` | Ollama models are pulled by tag from the Ollama registry. The digest is recorded after loading, not pinned before. GGUF downloads are already pinned by SHA-256. | A retagged model in the registry would be served without detection. | Record and compare the digest across deployments. Pinning Ollama manifests by digest is follow-up work. |
| G-22 | MEDIUM | Billing integrity | `server/app/api/v1/gateway.py` (usage parsing), `server/app/services/billing_service.py` | Token counts that drive token charges come from the provider's runtime through the tunnel. They are not verified, although they are labelled as such in the docs. | A malicious provider inflates output-token counts to raise its earnings. | Store counts as provider claims, cap them at what the response size permits, and add per-provider anomaly signals for operators. |
| G-23 | LOW | Transport limits | `server/app/services/tunnel.py:162` | The server-side WebSocket accepts frames up to uvicorn's 16 MiB default before the 2 MiB application check. | Memory pressure from a malicious node. | Set `--ws-max-size` to match the 2 MiB frame limit. |
| G-25 | MEDIUM | API | `server/app/main.py` (found by `server/tests/test_input_safety.py` during implementation) | A ~10 KB JSON body nested 5,000 levels deep raised `RecursionError` while being parsed or validated, and the request failed with a 500. | Cheap requests tie up workers and fill error logs (denial of service). | Refuse with 400 through a `RecursionError` handler. |
| G-24 | INFO | Secrets | History scan (§3) | No real secrets were found in git history. | — | Keep gitleaks on PRs. |

Routes still need a mechanical check that every non-public route is guarded. That check is added as a test (route enumeration) rather than asserted here.

## 3. Secret scan of the full history

- **Command:** a pattern scan of every blob reachable from every ref. It covers Paystack keys, MongoDB and Redis URIs with passwords, PEM private keys, AWS, GitHub and Hugging Face tokens, AgentMesh secrets, JWTs and long secret assignments. The script prints only the rule, commit, path and line.
- **Coverage:** 663 objects across 5 commits. gitleaks was not run locally because it is a binary download and this machine does not allow those without asking; CI runs it.
- **Result:** 12 hits. Every one is a placeholder or test fixture.
  - `.env.example` `SECRET_KEY` placeholder containing "change".
  - `client/e2e/README.md` fake Paystack key made of 5 distinct characters (`0aefk`), used only with the fake Paystack server.
  - MongoDB `user:pass@…example…` examples in `server/ops/backup_db.sh` and the migration script.
  - A test operator password in `server/tests/test_dashboards.py:175`.
- **Disposition:** no rotation needed. No values were printed or copied during the scan.

## 4. Assumptions requiring human verification

1. **Render (API):** `ENVIRONMENT` is set to `production`, `SECRET_KEY` is a random value of at least 32 characters, and the start command and proxy settings are unknown. Render's environment is managed by you, and I did not read it. Until G-01 ships, an unset `ENVIRONMENT` in production would be critical.
2. **Render proxy addresses:** the value to use for `FORWARDED_ALLOW_IPS` behind Render's proxy needs confirming from Render's documentation or support.
3. **MongoDB Atlas:** encryption at rest and backup retention and encryption are platform features I could not inspect.
4. **Vercel (dashboard):** the headers actually served.
5. **GitHub repository settings:** private vulnerability reporting, branch protection and required checks are not visible from the repository.
6. **Docker:** the workload isolation tests need a Docker daemon. This user cannot reach `/var/run/docker.sock` ("permission denied"), so those tests are written but skipped here.

## 5. Implementation order

1. G-01 (fail-closed environment).
2. G-02, G-03 (deployment exposure).
3. Authentication and tenant isolation:
   - route-enumeration test;
   - G-04 sessions with refresh rotation;
   - G-06;
   - G-07 (needs the new dependency approved);
   - G-05 MFA.
4. Node identity and authorization: G-09 quarantine, G-10 revocation bound, G-08 proof-of-possession sessions, G-11 signed commands.
5. G-18 worker hardening (code, with Docker tests skipped here).
6. Privacy: G-12 retention and deletion, G-13 canary tests.
7. G-14, G-15, G-22, G-23.
8. G-16, G-17 CI and supply chain.
9. Documentation: `SECURITY.md`, threat model, permissions, data handling, incident response, privacy notice.
10. Full test run, scanners, final report.
