# AgentMesh Threat Model

**Last updated:** 26 October 2026 (branch `security-hardening`)

This describes what AgentMesh defends against, where the trust boundaries are, and which risks are accepted. It reflects the code as implemented; controls are cited by file so they can be checked.

## 1. System overview

```
 customers / dashboard ──HTTPS──▶  control plane (FastAPI, MongoDB, optional Redis)  ◀──HTTPS + WSS (outbound)── provider workers
   (browser, API keys)              auth · billing · scheduler · gateway · ledger            │
                                                                                            ▼
                                                                         model runtime on the provider's machine
                                                                         (Ollama / llama.cpp / vLLM, loopback or internal network)
 Paystack ◀──HTTPS──▶ control plane (payments, refunds, payouts; signed webhooks)
```

- **Control plane** (`server/app`): accounts, deployments, the inference gateway, the worker protocol, billing and the ledger. API on Render, dashboard on Vercel, database on MongoDB.
- **Workers** (`server/node_agent`): run on machines owned by independent providers. They connect outbound only. They receive signed commands and proxy inference requests from the gateway to a local model runtime.
- **Workloads:** long-lived *deployments* of open-weight models, not one-shot jobs. A customer's requests reach the deployment through the gateway and the node's tunnel.

## 2. Trust boundaries

| # | Boundary | What crosses it | Controls |
|---|---|---|---|
| B1 | Internet → API | Every customer, provider and anonymous request | TLS (platform), authentication on every non-public route (enforced by `tests/test_route_guards.py`), rate limits, body-size limits, schema validation, CORS allowlist, security headers |
| B2 | Browser ↔ dashboard | Session tokens, user input | CSP (`client/src/lib/securityHeaders.ts`), HSTS, React escaping, 15-minute access tokens |
| B3 | Customer ↔ customer | Tenant data | Queries scoped by owner; other tenants' records answer 404 (`tests/test_tenant_isolation.py`) |
| B4 | Control plane ↔ worker | Commands, status, inference traffic | Node sessions by proof of possession, Ed25519-signed commands, revocation within 15 s (`app/services/worker_service.py`, `app/core/signing.py`, `node_agent/command_auth.py`) |
| B5 | Worker ↔ model runtime | Prompts, outputs, model files | Runtime on loopback or an `internal` Docker network, container limits (`node_agent/runtime/ollama_docker.py`), digest-verified model files (`node_agent/runtime/model_store.py`) |
| B6 | Provider ↔ their machine | Everything on it | **None that a root user cannot bypass** (accepted risk A1) |
| B7 | Control plane ↔ Paystack | Payments, refunds, payouts | HMAC-SHA512 webhook signatures, idempotent processing, reconciliation |
| B9 | Control plane → Gemini API (AI deployment agent, default provider) | The customer's AI request, planning conversation, short tool results | HTTPS, API key in a header (never a URL), redacted from logs; replies treated as untrusted and validated before any action (`app/services/ai/agent.py`); only the agent's data, never deployment prompts |
| B8 | Contributors ↔ CI/release | Code, dependencies, actions | SHA-pinned actions, read-only workflow tokens, no `pull_request_target`, scans on every PR, signed worker updates, provenance attestations |

## 3. Adversaries

| Actor | Assumed capability | Must not be able to | How (evidence) |
|---|---|---|---|
| Unauthenticated internet user | Arbitrary requests | Reach protected data or exhaust resources | Route guards and anonymous/forged-token tests (`tests/test_route_guards.py`); rate limits (`app/core/ratelimit.py`); body and WebSocket limits (`app/core/middleware.py`, `Dockerfile.server`); deep-nesting bodies refused (`app/main.py`) |
| Malicious customer | Valid account, crafted input, prompt injection | Access other tenants, escalate, manipulate billing, SSRF | Owner-scoped queries (`tests/test_tenant_isolation.py`); self-registration limited to customer/provider and strict schemas (`tests/test_input_safety.py`); server-side prices and bounded token claims (`app/services/billing_service.py`); model imports only from huggingface.co with no redirects (`app/services/huggingface.py`); model output is never interpreted (the gateway relays bytes) |
| Malicious provider | Root on its machine, modified worker | Get jobs not assigned to it, impersonate other nodes, inflate billing, persist after revocation | Commands leased per node and signed per node (`tests/test_node_sessions.py`); node-id header bound to the credential; token claims capped by observed sizes, plus an anomaly report (`tests/test_billing_integrity.py`); revocation and quarantine end sessions and tunnels (`tests/test_node_security.py`) |
| Compromised node credential | Stolen enrollment credential or session token | Stay usable past the revocation window | Sessions last 1 hour and need the node key. Revocation is immediate on HTTP and at most `TUNNEL_REVALIDATE_SECONDS` (15 s) on tunnels. With `ALLOW_LEGACY_NODE_CREDENTIALS=false`, the credential alone is useless. |
| Malicious model artifact | Crafted weights or metadata | Run code on load, escape the worker | Only GGUF (llama.cpp) and Ollama registry models; files pinned and verified by SHA-256; container limits. Residual: runtime parser bugs (A3). |
| Network attacker | Observes or modifies traffic | Read or alter traffic, replay commands | HTTPS required outside dev; workers refuse plain HTTP to non-local hosts unless explicitly allowed; signed commands with expiry and nonce; acks bound to the current nonce |
| Supply-chain attacker | Poisoned dependency, image or action | Reach secrets or ship unsigned artifacts unnoticed | Lock files, digest-pinned images, SHA-pinned actions, pip-audit, npm audit, Trivy, Bandit and gitleaks on PRs; signed worker updates; provenance attestations |
| Malicious contributor | Opens PRs from forks | Get CI secrets or trigger privileged workflows | `pull_request` only (no `pull_request_target`), `contents: read` tokens, release workflow only on maintainers' tags (`tests/test_ci_policy.py`) |
| Phished operator | Has an operator's password | Use staff powers | TOTP required for staff (`app/core/dependencies.py`, `app/services/mfa_service.py`) |

## 4. Assumptions

1. The hosting platforms (Render, Vercel, MongoDB Atlas) terminate TLS correctly and encrypt data at rest as they document. This was not verified from the repository.
2. `SECRET_KEY` and the optional `COMMAND_SIGNING_KEY` and `DATA_ENCRYPTION_KEY` are random, at least 32 bytes, held only in the platform's secret store, and never committed.
3. `FORWARDED_ALLOW_IPS` matches the hosting proxy, so client addresses used for rate limiting and audit are genuine.
4. Redis, when used, is reachable only by the API replicas and protected by a password.
5. Workers verify TLS certificates (httpx and websockets defaults; no verification bypass exists in the code).
6. The offline worker-release signing key is kept off the control plane.

## 5. Accepted risks

| ID | Risk | Why accepted | Mitigation |
|---|---|---|---|
| A1 | **A provider with root on its own machine can read the prompts and outputs that machine processes**, and the model files. | Inherent to running on community hardware without confidential computing. | Stated to customers (dashboard, docs, privacy notice). Providers never receive customer identity, email or billing data. Signed commands, quarantine and revocation limit abuse. Confidential computing (TEEs with attestation) or microVMs are future options for sensitive workloads. |
| A2 | Signatures and hashes prove a message is intact, not that the provider ran the requested model honestly or reported true token counts. | No practical verification exists yet. | Token claims capped by observed sizes, anomaly report, refunds. Future: redundant execution, canary prompts, reputation scoring. |
| A3 | Containers are not a strong boundary against a malicious host, and only a moderate one against a runtime exploit. Workloads run as the image's default user (root for `ollama/ollama`), GPUs are shared sequentially with limited memory isolation, and process-mode runtimes have no sandbox beyond the worker's OS user. | Needs runtime changes that require Docker to verify (not available during this work). | Capabilities dropped, no-new-privileges, read-only root, memory/CPU/PID limits, internal network, no Docker socket in workloads. Tests in `tests/test_worker_isolation_docker.py` run in CI. |
| A4 | Browser tokens live in `localStorage`. | Cross-site API and dashboard domains make cookie-based refresh fragile. | 15-minute access tokens, single-use refresh tokens with reuse detection, CSP restricting where scripts may send data. |
| A5 | The legacy `POST /nodes/register` path remains enabled. | The maintainer chose to keep it (26 October 2026). | Keys use SHA-256 secret hashes; nodes created this way cannot get node sessions without a registered key. |
