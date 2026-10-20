# AgentMesh Implementation Plan

Last updated: 2026-10-20. This file is the working record of what exists, what was changed, and what comes next.
It is updated at the end of every phase. Earlier design intent lives in
`AgentMesh MVP — Engineering Specification & Implementation Blueprint.md` and `AgentMesh_System_Architecture.md`.

## 1. Stack (as found)

| Area | Technology |
| --- | --- |
| Control plane | FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL 16, Redis (configured, unused) |
| Auth | JWT bearer tokens (python-jose), PBKDF2 password hashing (passlib) |
| Node agent | Python FastAPI app in `server/node_agent`, docker-py runtime adapters (Ollama, vLLM) |
| Frontend | Next.js 16, React 19, TanStack Query, Zustand, Tailwind, shadcn components |
| Tests | pytest + pytest-asyncio (server), Jest + Playwright (client) |
| CI | GitHub Actions: ruff, mypy, pytest, client lint/build/test, Docker builds, migration round-trip |

The backend is a modular monolith. That is the right shape for the MVP and will be kept.

## 2. Gap analysis (state before Phase 1)

Status key: **Works** = verified by a test or run. **Partial** = code exists, but key pieces are missing.
**Stub** = returns a canned value. **Fake** = reports success that did not happen. **Missing** = nothing exists.

| Capability | Status | Evidence |
| --- | --- | --- |
| Register / login / me | Works | Tests pass. But any caller could self-register as `admin` or `operator`. |
| Role-based authorization | Missing | No role checks on any route. |
| Model catalog | Partial | Table and list route exist. `POST /models` was unauthenticated, so anyone could add catalog entries. |
| Deployment create/list/get/stop | Partial | Rows are created, but nothing schedules or provisions them. `get` and `stop` had no ownership check (IDOR). |
| Inference | **Fake** | When a node had no URL, the control plane echoed the prompt back as the "result" and billed the customer. The node agent's `/inference` also echoed the prompt. A seeded "agentmesh-controlled-mvp" model was approved for this path. |
| Node registration | Partial | Provider registers and receives a hashed node key. Node detail was public and returned `api_key_hash`. The agent's own `register` CLI sends a payload the API rejects (missing `region`, `capabilities` list vs dict). |
| Heartbeat | Partial | Authenticated per node. Nothing marks stale nodes offline (background loops are empty `sleep` bodies). |
| Scheduler | Partial | Filters by status, region, and GPU/VRAM. No RAM/disk/runtime checks, no reservations, no "why not" reasons. |
| Worker protocol | Missing | Control plane would call *into* the node (inbound port 8001). No command queue, versioning, or idempotency. |
| Ollama runtime | Partial | Adapter starts `ollama/ollama:latest` with all GPUs, no resource limits, and `exec`s `ollama pull`. No readiness check, state is in memory only. |
| Docker worker | Partial | Compose mounts the host Docker socket into the agent and exposes an inbound port. |
| Installable agent | Missing | CLI exists, but no service install, enrollment, or uninstall. |
| Inference gateway / customer API keys | Missing | Only user JWTs exist. No scoped keys, rate limits, or streaming. |
| Usage metering | Partial | Token counts were estimated by splitting on whitespace. Agent usage reporter posts to a route that does not exist. |
| Wallet / payments | **Fake** | `POST /wallets/deposit` added any amount to any user's balance with no payment. No Paystack integration. |
| Audit log | Partial | Table and helper exist, never called. |
| AI agent routes | Stub | `/agent/*` returned `{"status": "ok"}`. |
| Frontend | Partial | Pages exist for all three roles. Landing page `LiveStats` shows hardcoded "live" numbers. |
| Local test infra | Broken | DB-backed test failed without a running Postgres. |

Other findings:

- `SECRET_KEY` defaulted to `supersecretkey` with no production guard. CORS allowed `*` with credentials.
- `workloads.status` was a `VARCHAR` in the migration but a native enum in the ORM, which breaks inserts on Postgres.
- Several indexes existed in migrations but not in the models, so `alembic revision --autogenerate` would have dropped them.
- `agent_service.deploy_model` calls `create_deployment` with arguments in the wrong order. It is dead code.

## 3. Phase 1 — Foundation and security (done)

Changes:

- **Roles.** Added a `require_roles` dependency. Self-registration is limited to `customer` and `provider`. Disabled users are rejected at token validation and login. User and profile are created in one transaction.
- **Ownership.** Deployment get/stop, usage, and node detail are scoped to the owner or staff. Non-owners get 404 so IDs cannot be probed. Node responses no longer include credential hashes. Malformed IDs return 404 instead of 500.
- **Catalog.** Only operators/admins can create models, and new entries start unapproved. Unapproved models are hidden from `GET /models/{id}` and cannot be deployed.
- **No fabricated results.** The echo paths are removed. Inference now fails with `NO_INFERENCE_ENDPOINT` and does not bill. The node agent returns 501. Migration `004` unapproves the placeholder model (kept, not deleted, to preserve foreign keys). `/agent/*` returns 501.
- **Test credits.** Deposits are labelled as unpaid test credits and are refused outside `dev`/`test` environments.
- **Config.** Startup fails outside dev/test if `SECRET_KEY` is the default or short, or if CORS contains `*`. Compose now requires `SECRET_KEY`.
- **Schema drift.** ORM indexes, `users.created_at` nullability, and the workload status type now match the migrations.
- **Tests and CI.** Test DB fixture uses `TEST_DATABASE_URL` (Postgres in CI) or in-memory SQLite. Added authorization, config, and no-fabrication tests. CI now runs `alembic check` for drift.

Verified locally: 39 pytest tests pass on SQLite, and ruff check and format are clean. Migrations 001, 002, and 004 apply on SQLite and `alembic check` reports no drift beyond SQLite's UUID typing. Migration 003 alters a foreign key, which SQLite cannot do, so it needs Postgres.
Not verified locally: the Postgres-backed CI run, mypy (not installed in the local venv), and Docker image builds (no Docker on the dev machine).

## 4. Phase 2 — First end-to-end Ollama deployment (done, with one environment gap)

Built on the existing FastAPI control plane and the `server/node_agent` package. Guides for users are in
[WORKER.md](WORKER.md) (providers) and [INFERENCE_API.md](INFERENCE_API.md) (developers).

**Control plane**

- **Worker protocol v1** (`app/api/v1/worker.py`, `app/services/worker_service.py`). Outbound-only. One-time
  enrollment tokens exchanged for a SHA-256-hashed node credential. Heartbeats with reconciliation, a long-poll
  command queue, status reports, graceful disconnect, and a WebSocket inference tunnel. Schemas reject unknown
  fields; bodies are capped at 256 KB; reported allocations are clamped to reported hardware.
- **Persisted command queue** (`node_commands`). Leases, bounded redelivery, idempotent acks.
- **Lifecycle state machine** (`app/services/deployment_lifecycle.py`). Compare-and-set transitions with an
  event history (`deployment_events`). Old status values are migrated.
- **Scheduler with reservations** (`app/services/scheduler_service.py`). Filters on freshness, pause state,
  region, runtime, GPU, and free CPU/RAM/disk/VRAM. Reserves with one conditional UPDATE so concurrent requests
  cannot oversubscribe. Failure responses explain why per category.
- **Catalog validation** (`app/services/catalog_service.py`). Approved models only, a supported runtime, a
  strict tag format, recorded requirements, and allowlisted config. Six Ollama models are seeded, with
  requirements marked as estimates.
- **Inference gateway** (`app/api/v1/gateway.py`). API key or user token, tenant isolation, model pinning,
  size, rate, and concurrency limits, and unbuffered streaming with timeouts and cancellation.
- **Metering.** One usage row per request, keyed by request id. Token counts are taken from the runtime's own
  report and labelled `runtime_reported`; when missing they stay null. No prompt or response content is stored.
- **API keys** (`/api/v1/api-keys`). Hashed, shown once, scoped, revocable.
- **Background monitors** (`app/background/monitors.py`) replace the empty loops. They mark stale nodes
  OFFLINE and their deployments UNHEALTHY (capacity is kept), fail stalled provisioning, expire leases, and
  time out unconfirmed stops.
- **Provider controls.** Enrollment tokens, pause/resume, and credential revocation, which fails the node's
  deployments and releases their capacity.
- Migration `005`. A dev SQLite initialiser is in `scripts/init_dev_db.py`.

**Worker** (`server/node_agent`, replaces the old inbound FastAPI agent)

- One code path for both modes. The process backend runs a dedicated `ollama serve` per deployment on a random
  loopback port with its own model directory, inside a systemd user scope with MemoryMax/CPUQuota. The Docker
  backend runs one hardened container per deployment.
- Readiness requires a successful test generation. The worker reports progress and runs local disk and memory
  checks before starting.
- State, credentials (0600), and processed command ids are persisted. After a restart the worker re-adopts live
  workloads and restarts dead ones. If its credential is revoked it stops everything and deletes the credential.
- Packaging: `Dockerfile.node-agent` (non-root, read-only), `docker-compose.worker.yml`, and a CLI with
  `enroll`/`start`/`run`/`status`/`hardware`/`uninstall`.

**Verification**

| Check | Result |
| --- | --- |
| Server and worker unit/integration tests (SQLite) | 115 passed, 1 skipped (concurrent-oversubscription test; runs on Postgres in CI) |
| End to end, real Ollama binary, agent mode | 14/14 checks. Real model download and cgroup-limited runtime. Deployment correctly **failed** with `HEALTHCHECK_FAILED` because the local Ollama install cannot run models (`llama-server` missing). Capacity released, runtime removed. |
| End to end, stub runtime, agent mode | 21/21 checks. Real worker, cgroups, WebSocket tunnel, gateway streaming (first chunk at 0.06 s of 0.16 s), API keys, tenant isolation, metering, delete, and cleanup |
| Crash recovery, stub runtime | Worker killed with SIGKILL: gateway returned 503, and after restart the live runtime was re-adopted and served again. Graceful exit marked the node OFFLINE at once |
| cgroup enforcement | MemoryMax, CPUQuota, and MemorySwapMax=0 confirmed on the runtime's scope |
| ruff, frontend `tsc` | Clean |

**Not verified**

- **Real inference.** No model has generated text through AgentMesh yet, because the installed Ollama is
  incomplete. Rerun `scripts/e2e_ollama.py` after reinstalling Ollama, or trigger the `e2e-real-ollama` CI job.
- **Docker worker.** There is no Docker on the dev machine. The `ollama/ollama:0.12.3` default tag, the
  read-only root filesystem for Ollama, and the image build are unverified. CI builds and smoke-tests the
  image.
- **Migration 005 on Postgres.** Its SQL was rendered offline and reviewed. CI's `e2e-stub-runtime` and
  `migrations-check` jobs apply it for real.
- **mypy.** It was already failing before Phase 2, with 39 errors, and now reports 95. Nearly all come from
  untyped `Column()` model declarations. Converting the models to SQLAlchemy 2.0 `Mapped[]` typing would clear
  them.
- The frontend Sidebar unit test fails, as it did before this work.

**Known limitations** (deliberately deferred)

- Tunnel routing, rate limits, and concurrency limits are in-process. Running more than one API replica needs
  Redis-backed routing and limits.
- Docker workloads have internet access, because they download their own models. An internal network with a
  separate pull step is planned.
- Docker workers do not detect GPUs. GPU scheduling therefore only works with manually allocated VRAM in agent
  mode, which is untested.
- Token counts are reported by the provider's runtime and are not independently verified. This must be
  addressed before payouts depend on them.
- No restart endpoint, multi-replica deployments, or rescheduling of failed deployments onto another node.
- The legacy `/inference` workload route still exists and always fails honestly. Remove it once the frontend
  moves to the gateway.

## 5. Next phases

### Phase 3 — Reliability and multi-node scheduling

Rescheduling failed or unhealthy deployments onto another node, a restart endpoint, Redis-backed tunnel
routing and rate limits for multiple API replicas, correlation IDs across gateway, worker, and runtime, audit
events for provider and operator actions, a Docker workload egress policy, and converting models to typed
SQLAlchemy declarations so mypy passes.

### Phase 4 — Installable node agent

Agent mode already works (see above). What remains: packaged installers (Linux systemd user unit, then macOS
launchd), a local status UI or tray, safe self-update, Windows support, and GPU detection beyond `nvidia-smi`.

### Phase 5 — Additional runtimes

Add llama.cpp (GGUF, CPU) and vLLM (GPU) behind `node_agent/runtime/base.py`. Catalog entries will list
compatible runtimes explicitly, and the scheduler will match on them.

### Phase 6 — Product experience

The frontend now uses the new status names but none of the new flows. Still to build: the deploy flow with
requirements and an untrusted-node warning, deployment progress and events, API key management, provider
enrollment and pause/revoke, real operator views, and replacing the hardcoded landing stats and operator
dummy rows.

### Phase 7 — Metering, pricing, and payments

Versioned pricing rules, separating measured usage from settled charges, Paystack in test mode with webhook
signature verification and idempotent processing, and payout states (pending, succeeded, failed, reconciled).

## 6. Trust model (to be surfaced in the product)

On ordinary community nodes, the provider can inspect model files, process memory, and any prompt or output the workload handles. Docker isolation does not prevent this. AgentMesh will not claim otherwise. Confidential computing (TEE + attestation + key release) is a future tier and is not implemented.
