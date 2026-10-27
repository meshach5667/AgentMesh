# AgentMesh Permissions

**Last updated:** 26 October 2026

Authorization is enforced on the server for every request: through `get_current_user` / `require_roles` (`server/app/core/dependencies.py`) for users, `current_node` / `enrolled_node` (`server/app/api/v1/worker.py`) for workers, and in-handler checks for the gateway, metrics and Paystack webhook. `server/tests/test_route_guards.py` fails if a route is neither guarded nor on the reviewed public list. Records belonging to another tenant answer **404**, so their existence is not confirmed.

## Principals

| Principal | How it authenticates | Lifetime |
|---|---|---|
| Customer, provider | Email + password (Argon2id) → access token (JWT, 15 min) bound to a server-side session; single-use refresh token | Session ends at logout, logout-all, refresh-token reuse, account disable, or after 14 days |
| Operator, admin (staff) | As above **plus TOTP**: staff routes refuse sessions that have not completed MFA while `STAFF_MFA_REQUIRED` | Same |
| API key (`am_sk_…`) | Bearer key, stored as SHA-256 | Until revoked or its expiry; optional binding to one deployment; scope `inference` |
| Node (worker) | Node session token (1 h) obtained by signing a challenge with the node's private key plus the enrollment credential; or the enrollment credential alone while `ALLOW_LEGACY_NODE_CREDENTIALS` | Session 1 h; ended by revocation or quarantine |
| Paystack | HMAC-SHA512 webhook signature | Per request |
| Metrics scraper | `METRICS_TOKEN` | Until rotated |

## What each role can do

| Capability | Customer | Provider | Operator / Admin | Node | Anonymous |
|---|---|---|---|---|---|
| Register, sign in | ✓ (customer/provider roles only) | ✓ | provisioned with `scripts/create_operator.py` | — | ✓ |
| Browse catalog, public prices, public stats | ✓ | ✓ | ✓ | — | ✓ |
| Create, view, stop, restart, delete **own** deployments | ✓ | — | view all | — | — |
| Call **own** deployments through the gateway | ✓ (token or API key) | — | — (staff not exempt) | — | — |
| Manage **own** API keys | ✓ | — | — | — | — |
| Own AI agent runs: create, view, cancel, delete when finished | ✓ | — | view | — | — |
| Wallet, top-ups, own charges, refunds, transactions, CSV export | ✓ | ✓ (earnings, payouts) | all, via admin views | — | — |
| Enrollment tokens, **own** nodes: pause, resume, community-model opt-in, revoke | — | ✓ | opt-out and revoke any | — | — |
| Quarantine and release nodes | — | — | ✓ | — | — |
| Pricing, commission, model approval, payouts, refunds, reconciliation, audit log, sponsorships, anomaly report | — | — | ✓ | — | — |
| Heartbeat, poll and ack **own** commands, report **own** deployments' status, open tunnel | — | — | — | ✓ (own node only) | — |
| Obtain a node session | — | — | — | ✓ (enrollment credential + node key) | — |

Rules that hold across roles:
- Clients cannot set roles, owners, node ownership, prices, capacity, statuses or usage. Strict schemas (`extra="forbid"`) reject unknown fields, and server-owned fields are ignored on create (`server/tests/test_input_safety.py`).
- A provider never sees customer identity, email or billing data. Commands carry only the model, its source and digest, and resource limits.
- Staff cannot opt a provider's node *in* to community models; only the provider can consent.

## Worker (on the provider's machine)

The worker runs as an unprivileged user (`Dockerfile.node-agent`: UID 10001, read-only root, all capabilities dropped). It can:
- create and remove the containers or processes it labels as its own, and no others;
- download model files only from allowlisted hosts, verified by SHA-256;
- act only on commands carrying a valid signature for this node (`server/node_agent/command_auth.py`).

The Docker worker needs the Docker socket, which is **root-equivalent on the host**; prefer rootless Docker on a dedicated machine.

## Workload containers

Workload containers get: all capabilities dropped, `no-new-privileges`, a read-only root filesystem with a capped tmpfs, memory (no swap), CPU and PID limits, no host mounts except the AgentMesh model cache volume, no Docker socket, and an `internal` network with no route out once serving (`server/node_agent/runtime/ollama_docker.py`, `workload_limits`). They receive no platform secrets or node credentials, only runtime settings. Known gaps: workloads run as the image's default user, and GPU deployments see all GPUs (see THREAT_MODEL.md, A3).
