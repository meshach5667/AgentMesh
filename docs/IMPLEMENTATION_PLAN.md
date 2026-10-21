# AgentMesh Implementation Plan

Last updated: 2026-10-20 (after Phase 5). This file is the working record of what exists, what was changed, and what comes next.
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

## 4. Phase 2 — First end-to-end Ollama deployment (done)

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

| End to end, **real inference** (rerun after Ollama was reinstalled, start of Phase 3) | 21/21 checks. `smollm2:135m` READY in 91 s; streaming chat (41 chunks, first at 0.30 s) and OpenAI-compatible completion through the gateway; tokens metered as reported by Ollama |

**Not verified**

- **Docker worker.** There is no Docker on the dev machine. The `ollama/ollama:0.12.3` default tag, the
  read-only root filesystem for Ollama, and the image build are unverified. CI builds and smoke-tests the
  image.
- **Migration 005 on Postgres.** Its SQL was rendered offline and reviewed. CI's `e2e-stub-runtime` and
  `migrations-check` jobs apply it for real.
- **mypy** reported 95 errors at the end of Phase 2 (fixed in Phase 3).
- The frontend Sidebar unit test fails, as it did before this work.

Phase 2's known limitations are tracked, as updated, in the Phase 3 section below.

## 5. Phase 3 — Reliability and multi-node scheduling (done)

**Implemented**

- **Moving deployments off failed nodes** (`app/services/placement_service.py`). These failures are the
  node's fault: unresponsive, offline, revoked, stalled provisioning, unhealthy beyond
  `UNHEALTHY_GRACE_SECONDS` (default 180 s), out of memory or disk, or a runtime that won't start. On any of
  them the deployment is placed on another node with the **same id, endpoint, and API keys**. Nodes that
  failed it are excluded, and placements are capped by `MAX_SCHEDULE_ATTEMPTS` (default 3). Failures caused
  by the model (bad tag, failed test generation, download errors that persist after retries) still end in
  `FAILED`. If no node is left, the error explains why. The lifecycle gained the matching transitions, a
  partial unique index allows one ACTIVE reservation per deployment while keeping history (migration `006`),
  and every move is audited.
- **Node-loss handling.** A stale or gracefully disconnected node has its provisioning work moved at once.
  Serving deployments get the grace period first, so brief outages don't cause a move.
- **Restart** (`POST /deployments/{id}/restart`). A `RESTART` command stops and redeploys on the same node
  from the cached model, keeping capacity reserved. Stale worker reports can no longer move a serving
  deployment backwards.
- **Download retries on the worker.** Transient registry and network errors are retried with backoff, while
  "model does not exist" errors fail at once.
- **Correlation ids.** Every request gets a server-generated `X-Request-ID`. Client-supplied ids are not
  trusted, because the id is also the metering key. The id appears in JSON logs, the gateway response, the
  tunnel frame, worker logs, usage records, and audit entries.
- **Secret redaction** in all log output: API keys, node credentials, enrollment tokens, bearer tokens, and
  password-like fields.
- **Audit trail** (`app/services/audit_service.py`, `GET /admin/audit-logs` for operators). Registration and
  logins (including failures), enrollment, pause/resume/revoke, deployment create/stop/restart/delete/move,
  API key create/revoke, catalog create/approve, and test credits are recorded in the same transaction as
  the action.
- **Multiple API replicas** (`COORDINATION_BACKEND=redis`). Rate and concurrency limits are shared through
  Redis, and concurrency slots expire so a crashed replica can't leak them. Each tunnel's owning replica is
  recorded in Redis. Gateway requests, response chunks, cancellations, and revocations travel between
  replicas over pub/sub. One replica at a time runs the background monitors. Single-process deployments need
  no Redis.
- **Docker workload egress.** With the Compose setup, serving containers live on an internal network with no
  route out. They join an egress network only while downloading the model and are disconnected before
  serving. A non-internal workload network is refused.
- **Typed models.** All models use SQLAlchemy 2.0 `Mapped[]` declarations. The generated Postgres DDL is
  byte-identical to before. **mypy now passes with 0 errors** (95 before), and it found two real bugs on the
  way: the marketplace listing crashed whenever a node existed, and a dead `agent_service` called
  `create_deployment` with its arguments swapped (it was removed).
- **Config safety.** Startup rejects a heartbeat timeout shorter than three heartbeat intervals. This caught a
  misconfiguration in the first failover run.
- **Hygiene.** Deprecated `utcnow` was replaced. Pytest now turns deprecation warnings from our own code
  into errors, where previously a run produced 2,000+ warnings.

**Verification**

| Check | Result |
| --- | --- |
| Unit and integration tests (SQLite) | 152 passed, 1 skipped (concurrency test; Postgres in CI) |
| ruff, ruff format, **mypy**, frontend `tsc` | All clean |
| Real failover: two workers, real Ollama (`scripts/e2e_failover.py`) | 18/18 checks. Node A killed hard; gateway answered 503 `node_unavailable`; deployment moved to node B and served again in 111 s (including node B's model download) with the same id, endpoint, and API key. The history showed `READY -> UNHEALTHY -> SCHEDULED -> PROVISIONING -> STARTING -> READY`. A real restart produced a new runtime process, and no processes were left behind |
| Real single-node end to end (regression) | 21/21 checks with real inference |
| Multi-replica routing and limits | 9 tests against fakeredis, including the full gateway path through a second replica |
| Docker egress isolation | Unit-tested with a fake Docker client (connect for download, disconnect before serving, also on failure) |

**Not verified**

- **Two real replicas on real Redis.** The new `e2e-multi-replica` CI job does this on PostgreSQL and Redis.
  There is no Redis on the dev machine.
- **Migrations 005 and 006 on PostgreSQL.** Their SQL was rendered offline and reviewed. CI applies them.
- **Docker worker and egress isolation on a real daemon.** There is still no Docker on the dev machine.

**Known limitations**

- Docker workers do not detect GPUs, and GPU scheduling is untested on real hardware.
- Token counts are reported by the provider's runtime and are not independently verified. This must be
  addressed before payouts depend on them.
- A deployment runs on one node at a time. There is no multi-replica serving or load balancing across nodes.
- Customer-initiated restarts are refused while the node is offline. The automatic move handles that case.
- Moving a deployment re-downloads the model on the new node, so it takes about one download time.
- The legacy `/inference` workload route still exists and always fails honestly. Remove it with the
  frontend work.

## 6. Phase 4 — Installable node agent (done for Linux; macOS untested)

**Implemented**

- **Packaging** (`server/scripts/build_worker_wheel.py`). A reproducible `agentmesh-worker` wheel containing only
  `node_agent`, with an `agentmesh-worker` command. Building needs no network or build backend, and two builds
  are byte-identical. Control-plane code never ships to providers.
- **Installer and uninstaller** (`server/packaging/install.sh`, `uninstall.sh`). Per-user, refuses root, and
  checks the OS, Python 3.11+, `venv`, and Ollama. It never installs or changes Ollama. It creates a private
  environment, writes a 0600 config file, caches the wheel for rollback, enrolls, and installs the service.
  The uninstaller stops the service and workloads and removes credentials, config, the environment, and
  optionally models.
- **Background service** (`node_agent/service.py`). A systemd user unit on Linux (`Restart=on-failure`,
  `NoNewPrivileges`, `PrivateTmp`, optional lingering) or a launchd agent on macOS (`KeepAlive` on crash). The
  `agentmesh-worker service install|uninstall|status` command manages it.
- **Config file** (`~/.config/agentmesh/*.env`). Environment variables override it.
- **Local control.** `pause` stops new work, `drain` also stops running work so it moves to other nodes, and
  `resume` undoes both. **Availability schedules** (`AGENTMESH_AVAILABILITY_SCHEDULE`, e.g.
  `mon-fri 18:00-08:00`, including overnight windows) can either pause or drain outside the window. The
  worker reports availability in its heartbeat, and the scheduler requires both the dashboard pause and the
  worker to allow work (migration `007`). Deploy commands that race with a pause are handed back and placed
  elsewhere (`NODE_UNAVAILABLE`).
- **`agentmesh-worker doctor [--deep]`**. Read-only diagnosis with a concrete fix per problem: platform,
  Python, config, control plane, credential (new read-only `GET /worker/whoami`), Ollama, cgroup limits,
  Docker access, disk, memory headroom, GPUs, schedule. `--deep` starts a throwaway Ollama instance on a
  random port with a scratch model directory.
- **Richer `status`**: connection, last heartbeat, local pause/drain state, schedule and next change, and
  workloads.
- **GPU detection**: NVIDIA (each GPU listed separately), AMD via `rocm-smi`, and Apple Silicon (shared memory,
  estimated usable VRAM), with timeouts and tolerance for garbage output.
- **Signed self-update** (`node_agent/updater.py`, `scripts/sign_worker_release.py`). Ed25519 release manifests
  are signed offline and checked against a key pinned on each worker, so the control plane only relays them
  (`GET /worker/releases/latest`, `/worker/releases/files/{wheel}`, filename-checked). The updater refuses
  downgrades, checks the SHA-256, installs into the worker's own environment, probes the new version, and
  rolls back to the cached previous wheel. Heartbeats announce the latest version. Optional
  `AGENTMESH_AUTO_UPDATE` applies updates only while idle, then exits with code 75 so the service manager
  restarts it.
- **Windows is refused explicitly** with a pointer to the Docker worker.

**Verification**

| Check | Result |
| --- | --- |
| Unit and integration tests | 196 passed, 1 skipped |
| ruff, mypy, frontend `tsc`, shell syntax | Clean |
| Real `install.sh` on this machine (test service `agentmesh-worker-e2etest`) | Service active; config 0600, data dir 0700; `doctor` all OK including enforced cgroup limits inside the service |
| Real deployment through the installed service | `smollm2:135m` READY, real inference ("Hello, how can I assist you today?"), runtime in its own `agentmesh-wl-*` scope |
| Local pause / resume / drain against the real control plane | Paused: node unavailable, running deployment kept serving, new deployment refused. Drain: workload stopped and handed back; with no other node it failed with an explanation |
| Real signed updates | A tampered manifest was refused. 0.3.0 to 0.3.1 applied and seen by the control plane after restart. A deliberately broken 0.3.2 **rolled back to 0.3.1 automatically** and the service kept running |
| Real `uninstall.sh` | Service, config, environment, data, and processes all gone; the systemd user directory is identical to the pre-install snapshot |

Two bugs were found by the real runs and fixed with regression tests:

- **Wrong version probe.** The updater's version check could import a stray `node_agent` from the current
  directory, which reported a successful update as failed. It now runs isolated (`python -I`).
- **Leftover config folder.** The uninstaller left an empty config directory behind.

**Not verified**

- **macOS.** The launchd plist is generated and validated with `plistlib`, but has never run on a Mac.
- **AMD and Apple GPU detection.** Tested only against recorded tool output; there is no such hardware here.
- **The Docker worker.** Docker is installed, but this account is not in the `docker` group, so the socket is
  denied. `doctor` reports exactly that. After `sudo usermod -aG docker $USER` and a re-login, run
  `docker compose -f docker-compose.worker.yml up` plus `scripts/e2e_ollama.py --mode docker`.
- **The installer CI job.** It is new and has not run yet.

**Known limitations**

- No tray or graphical status app; `status` and `doctor` are command-line only.
- Windows is not supported (use the Docker worker).
- macOS resource limits are advisory.
- The installer needs network access to PyPI for the worker's dependencies; there is no offline wheelhouse yet.
- Releases are signed with a single key. Key rotation means reinstalling or editing the pinned key on each
  machine.

## 7. Phase 5 — Additional runtimes (llama.cpp verified; vLLM not run on GPU hardware)

**Implemented**

- **Explicit compatibility catalog** (`model_artifacts`, migration `008`). Each (model, runtime) pair has its
  own artifact recording:
  - the source: an Ollama tag, or a Hugging Face repository pinned to a 40-character commit;
  - for GGUF files, the file name, SHA-256, and size;
  - resource needs, the GPU requirement, and an operator enable switch;
  - `last_ready_at`, set when a deployment of it passes the readiness test.

  The seeds were fetched from the Hugging Face API on 2026-10-20, all ungated and Apache-2.0: SmolLM2 135M
  and Qwen2.5 0.5B GGUFs for llama.cpp, and Qwen2.5 0.5B and 1.5B Instruct for vLLM. Operators manage
  artifacts with `POST /models/{id}/artifacts` and `PATCH .../artifacts/{id}`, using the same validation as
  deployments, and every change is audited. The migration is plain SQL, so it renders offline.
- **Runtime-aware deployment.** `runtime` is optional on `POST /deployments`. Without it, AgentMesh tries
  `ollama`, then `llamacpp`, then `vllm`, and uses the first that fits. Reservations come from the chosen
  artifact, so the llama.cpp GGUF reserves 512 MB where Ollama reserves 768 MB. Failure responses include
  `by_runtime` reasons. A runtime the model lacks is rejected with the runtimes it does have.
- **Gateway.**
  - `/deployments/{id}/v1/*` (OpenAI-compatible) works for every runtime, and responses include
    `openai_base_url`. `/ollama/*` stays Ollama-only and points other runtimes to `/v1`.
  - Path allowlists are per runtime and are enforced again on the worker.
  - Streaming `/v1` requests ask for `include_usage`, so token counts are metered on every runtime.
- **Worker runtime registry.** Shared process supervision (`runtime/process_utils.py`: cgroup scopes,
  PID-reuse-safe ownership, process-group termination) now backs:
  - `OllamaProcessRuntime` (refactored);
  - `LlamaCppProcessRuntime` (`llama-server`);
  - `VLLMProcessRuntime` (`vllm serve`);
  - `VLLMDockerRuntime` (`vllm/vllm-openai`), which reuses the Ollama container hardening and egress cut.

  Each runtime reports availability honestly. Deploy commands are validated per runtime, and vLLM refuses
  anything without a GPU.
- **Model store** (`runtime/model_store.py`).
  - Downloads use https and allowlisted hosts only, with every redirect checked, so there is no SSRF route.
  - Files are verified by SHA-256 and size and stored content-addressed; interrupted downloads resume.
  - Gated or private models are refused, because no tokens go to nodes.
  - Transient errors are retried by the worker's existing backoff.
- **Failure policy.** `RUNTIME_UNAVAILABLE` and `WORKER_ERROR` move the deployment to another node.
  Integrity and access errors fail it.

**Verification**

| Check | Result |
| --- | --- |
| Unit and integration tests | 245 passed, 1 skipped |
| ruff, mypy, frontend `tsc` | Clean |
| **Real llama.cpp end to end** (`e2e_ollama.py --runtime llamacpp`, using the `llama-server` bundled with the local Ollama 0.40.6) | 23/23 checks. GGUF downloaded from Hugging Face at the pinned commit; digest `sha256:5a1395…ba83` matched the catalog; READY in 146 s after a real test generation; streaming `/v1/chat/completions` (first chunk 0.15 s); Ollama route refused; streamed and non-streamed usage metered; delete cleaned up |
| Real Ollama end to end (regression) | 22/22 checks |
| Refactored Ollama process runtime | Real instance in a 900 MB `MemoryMax` scope, removed cleanly |
| Migration `008` | Rendered offline for PostgreSQL and reviewed |

The real runs exposed three bugs, all fixed with regression tests:

- **Rejected runtime names.** The protocol schema accepted only `ollama`, so heartbeats listing other
  runtimes would have been rejected.
- **Incomplete enrollment.** Enrollment registered only the first runtime.
- **Stranded deployments.** The GGUF download misused an httpx streaming response, and the worker let that
  unexpected error escape. The deployment would have sat in PROVISIONING until the stall timeout. The worker
  now reports any unexpected failure as `WORKER_ERROR` and cleans up.

**Not verified**

- **vLLM** on real hardware; there is no NVIDIA GPU here. The adapters are unit-tested with fakes only, and
  the default `vllm/vllm-openai:v0.10.1` tag is unverified.
- **llama.cpp with an official release binary.** Verification used Ollama's bundled `llama-server` build
  (llama.cpp server 0.7.0-dev), which takes the standard flags.
- **Docker variants** (vLLM container, Ollama container). The account still lacks Docker socket access.
- **Migration `008` applied to PostgreSQL.** It will run in CI's migration and end-to-end jobs.

**Known limitations**

- llama.cpp is offered by the installable agent only; there is no llama.cpp container for the Docker worker
  yet.
- Gated models (for example Meta Llama on Hugging Face) are not supported by llama.cpp or vLLM.
- vLLM downloads full repositories and is verified only by the pinned commit, not by per-file hashes.
- A move after a failure keeps the same runtime; it does not switch, for example, from vLLM to llama.cpp.

## 8. Phase 6 — Product experience (done)

**State before this phase.** Most dashboard screens showed hardcoded demo data:

- operator overview figures (142 nodes, $45,200 revenue) and dummy operator tables;
- a fake Visa card and spend rate;
- a scripted "agent orchestrator log";
- fake node gauges and hardware, and a fixed earnings chart;
- landing-page counters that increased at random;
- a hero animation of invented H100 nodes.

Several data hooks also replaced API failures with zeros or empty lists. None of the backend flows from
phases 2 to 5 had screens, and there was no way to create an operator account.

**Implemented**

- **Backend read APIs** (`services/reporting_service.py`):
  - `GET /stats/public`: unauthenticated counts only (nodes online, GPU nodes, runtimes online, deployable
    models, ready deployments), plus flags for which features are enabled.
  - `GET /usage/summary`: requests, failures and runtime-reported tokens per day and per deployment. It is
    scoped to the caller's deployments (customer), the caller's nodes (provider), or the whole network (staff
    only).
  - `GET /admin/overview`, `/admin/nodes` (with owner email), `/admin/deployments` (with customer email,
    filterable), `/admin/models` (including unapproved), and `/admin/transactions`.
  - `GET /usage/{id}` gained `limit`.
  - `/earnings` now returns real hosted-deployment counts; they were hardcoded to 0.
- **Operator bootstrap.** `scripts/create_operator.py` creates or promotes an operator or admin account from
  the server, with a 12-character minimum password, and audits it as `user.operator_provisioned`.
- **Customer flows.**
  - A searchable catalog showing per-runtime artifacts, which runtimes are online, and last verified readiness.
  - A deploy form: runtime choice or automatic, context window, region, GPU, a live reservation estimate using
    the scheduler's formula, a mandatory trust acknowledgement, and an idempotency key. A 503 is explained per
    runtime.
  - A deployment page: polls every 2 s while starting, shows the event timeline, status explanations, error
    codes, verified digest, endpoints, copy-paste examples (curl, Python, streaming, Ollama), and a "Try it"
    box that sends a real metered request. Stop, restart and delete are shown only where the server allows
    them.
  - API key management: deployment scoping, expiry, show-once secret, revoke.
  - A usage page.
  - A wallet that is honest about payments: test credits only when the server enables them.
  - A real ledger.
- **Provider flows.**
  - Enrollment: a one-time token, then the install command for the agent or the Docker worker with this
    network's address and the token filled in.
  - A node list and node page: availability that mirrors the scheduler's checks (paused, unavailable on the
    machine, offline, revoked), reserved versus allowed capacity, reported runtimes, whether limits are
    enforced or advisory, and machine load. Pause, resume, and revoke with confirmation.
  - Served usage, earnings, and ledger pages, with payouts marked as planned.
- **Operator flows.** Overview (including nodes whose heartbeats are overdue), all nodes (pause, resume,
  revoke), all deployments (stop), model catalog (approve, enable or disable artifacts), network usage,
  ledger, and an audit log search.
- **Honesty.** All hardcoded figures, rows and logs were removed. The landing page shows live counts, a "what
  works today / planned" list, and the trust model; its schematic is labelled as an illustration. Hooks
  surface API errors instead of returning zeros. Planned features (payments, payouts, confidential computing)
  are labelled where they would appear.
- **Navigation.** Role-aware routing sends each role to its own area; the API still authorizes every
  request. Admins now land on the operator dashboard. Sidebar links point only at pages that exist, and a
  navigation strip replaces the sidebar on small screens.
- **Docs.** New `docs/GETTING_STARTED.md` (all three roles, the status table, the trust model).
  `INFERENCE_API.md` covers usage summaries. The README describes the product accurately and links the
  operator bootstrap and the browser test.

**Verification**

| Check | Result |
| --- | --- |
| Backend unit and integration tests | 252 passed, 1 skipped (7 new: public stats contain counts only, usage scoping across tenants and roles, staff-only operator APIs, operator views, hosted-deployment counts, operator bootstrap) |
| ruff, ruff format, mypy | Clean |
| Frontend `tsc`, production `next build` | Clean; 29 routes built |
| Frontend unit tests (jest) | 16 passed: error parsing, reservation formula parity, API examples, UTC parsing, node availability, deploy form (acknowledgement gate, payload, per-runtime 503), sidebar |
| **Browser end to end** (`client/e2e/product.spec.ts`; installed Google Chrome; real control plane, real installable-agent worker, real SmolLM2 135M on an isolated Ollama instance) | 8/8 passed in 6.0 min. The run went: landing page shows live counts → provider signs up, creates a token in the UI, and the worker enrolls with it → node shows "Accepting work", then pause and resume → customer deploys from the catalog (deploy disabled until the trust acknowledgement) → READY after a real test generation (5 min 23 s including the model download), with the digest shown → "Try it" answers → scoped API key created in the UI and used for a real request → usage page shows 2 requests → operator sees the network, the customer and provider emails, and the audit log; a customer sent to `/operator` is redirected → delete → worker stops the runtime and the node's reservation returns to 0 |

The database after the run matched what the UI showed:

- two metered requests (42/8 and 32/8 tokens, runtime-reported), one through the user session and one
  through the API key;
- the deployment `STOPPED` with cleanup `done`;
- one audit entry for each action.

The browser test found only test-selector mistakes; it found no product bugs.

**Not verified / known limitations**

- Only Chrome on Linux at desktop width was exercised in the browser test. The narrow-screen navigation is
  untested in a real browser.
- The dashboard has no forms for adding a model artifact or changing account details; both use the API.
- Usage summaries are aggregated by SQL on each request. At high volume they will need rollups.
- ESLint went from 16 problems to 2. Both remaining ones pre-date this phase and were left unchanged:
  - an error in `providers/ThemeProvider.tsx` (setState inside an effect);
  - a warning about the `window.location` redirect on 401 in `lib/api.ts`.

## 9. Phase 7 — Payments and production readiness (done; Paystack verified against a stand-in only)

**State before this phase.**
- Wallets had balances, but nothing charged deployments.
- `payment_service.settle_usage` had no callers.
- The legacy workload path changed balances without ledger keys, behind code that always fails.
- There was no payment provider, no pricing, no readiness check, no metrics, no backups, and no throttling on
  login.

**Implemented**

- **Ledger** (`services/ledger_service.py`).
  - It is the only code that changes balances. Each change is an atomic SQL increment, and every posting has
    a unique idempotency key.
  - The invariant: balance = settled credits − (pending + settled) debits.
  - Both old money paths were removed.
  - Migration `009` relabels existing (test-credit) wallets into `BILLING_CURRENCY` (default NGN).
- **Pricing** (`pricing_rules`). Versions are immutable and cannot be backdated; each sets CPU-core-hour,
  RAM GB-hour, VRAM GB-hour, per-million input and output token prices, and the platform fee. Operators
  publish them in the dashboard; there is no seed price. Until one exists, usage is measured but free.
- **Rating** (`services/billing_service.py`, every `BILLING_INTERVAL_SECONDS`).
  - Each deployment's window `[metered_until, now)` is priced from READY intervals rebuilt from the
    control plane's lifecycle events (now stamped with the node) and from runtime-reported tokens.
  - Output tokens are capped at the response bytes the gateway counted.
  - Windows are split at price changes and node moves. Usage records stay separate from `charges`, which
    keep the quantities, the price version, and the split.
  - A unique key per (deployment, node, period) and a compare-and-set on the watermark rule out double
    charging.
- **Prepaid enforcement.** A deployment needs balance for `BILLING_MIN_PREPAID_HOURS` of its reservation;
  otherwise the request gets a 402 and the reservation is rolled back. Running out of balance stops the
  customer's deployments with `INSUFFICIENT_FUNDS`.
- **Paystack** (`services/paystack.py`, `services/payments_service.py`).
  - Top-ups: checkout initialize, verify on return, and HMAC-SHA512-signed webhooks with an idempotent inbox.
    Credit happens exactly once, after the amount and currency match; a mismatch goes to `REVIEW`.
  - Payouts: account verification and transfer recipients (last four digits stored), a hold on request,
    operator approval, transfers, and transfer webhooks. Failed, reversed or rejected payouts return the
    funds; unknown outcomes stay held.
  - Test mode is enforced unless `PAYSTACK_ALLOW_LIVE`.
- **Reconciliation** (`services/reconciliation_service.py`). Stale open items are settled with Paystack every
  10 minutes. A read-only report checks wallet balances against the ledger, the split of every charge,
  credited-once top-ups, and payout holds. It has an operator page.
- **Dashboard.**
  - Customers: a wallet with Paystack top-up and return verification, prices, charges, hourly prices in the
    deploy form, and charges on the deployment page.
  - Providers: earnings, the payout account, payout requests and history.
  - Operators: pricing, payout approval, reconciliation.
  - All "not available yet" notices for payments were replaced.
- **Production readiness.**
  - `/health/ready` (database, plus Redis when used) and token-protected `/metrics` (Prometheus).
  - Security headers on the API (pure ASGI, so streaming is untouched) and on the dashboard.
  - Login and registration throttling, Paystack key redaction, and an https `PUBLIC_BASE_URL` required in
    production.
  - Production compose: required URLs, Paystack settings, readiness healthcheck, and proxy headers.
  - `ops/backup_db.sh` and `ops/restore_db.sh`, plus a CI backup and restore round trip.
  - `scripts/paystack_smoke.py` for checking against Paystack's real test API.
  - Docs: `docs/OPERATIONS.md` and `docs/SECURITY_REVIEW.md`.

**Verification**

| Check | Result |
| --- | --- |
| Backend tests | 280 passed, 1 skipped (30 new). Coverage: READY-interval reconstruction; charge amounts and fee split; idempotent re-runs; price-change splits; unhealthy time not charged; the output-token cap; the prepaid 402 releasing capacity; exhausted balance stopping deployments; pricing authorization and no backdating; the ledger idempotency key; tamper detection; signed and unsigned webhooks; redelivery; verify and webhook in both orders; amount mismatch; reconciliation of abandoned and late payments; payout hold, approve and success; failed, reversed and rejected refunds; uncertain transfers reconciled rather than refunded; settings validation; readiness; metrics auth; login throttling; redaction |
| ruff, ruff format, mypy | Clean |
| Frontend `tsc`, `next build`, jest | Clean; 21 jest tests (5 new: pricing formula parity with the server, checkout-URL allowlist, return-reference validation) |
| **Browser end to end** (installed Chrome; real control plane, worker and SmolLM2 model; Paystack replaced by `tests/fixtures/fake_paystack_server.py`, which sends signed webhooks over HTTP) | 10/10 in 1.9 min. The operator publishes prices in the UI → the customer tops up 2,000 NGN (stubbed hosted page, signed `charge.success` webhook, verify on return) → the deploy form shows the hourly price → the real deployment goes READY, answers, and is charged → the provider adds a bank account, requests a payout, the operator approves, a signed `transfer.success` arrives → SUCCEEDED → reconciliation reports the ledger consistent |

The database after the run matched the price list:

- 12.7 s of READY time over two windows, matching the 13 s between READY and stop. The 1.4-minute model
  download was not charged.
- 825 NGN/h × 7.97 s = 1.826 NGN, plus 74/25 tokens = 0.248 NGN.
- Customer balance 2000 − 3.146 = 1996.854. Provider: 0.9 of the charges − 1 NGN payout = 1.832.
- Each webhook processed once. Reconciliation `ok: true`.

**Not verified**

- **Paystack's real API.** No keys were available. Run `scripts/paystack_smoke.py` with a test key and
  deliver a real webhook before relying on payments.
- **Migration `009` and the backup round trip on PostgreSQL.** Rendered offline and reviewed; they run in CI.
- **Billing with several API replicas.** Its safety rests on database compare-and-set and unique keys,
  tested on SQLite.

**Known limitations** (details in `docs/SECURITY_REVIEW.md`)

- Token counts and READY state still depend on provider-side reports. The output-token cap bounds this; it
  does not prevent it.
- There are no refunds or ledger corrections; they need a new code path.
- One platform currency. Paystack "OTP required" transfers need operator action in Paystack.
- Session tokens in `localStorage` without a CSP. No MFA for operators.
- Provider-set node prices (`node_pricing`) are ignored; the platform price list applies.

## 10. Next steps

- **Run against Paystack test mode with real keys:** run the smoke script, a dashboard top-up with a webhook,
  and one payout.
- **Ledger corrections and refunds:** an operator-initiated adjustment posting, with an audit trail.
- **Independent checks on provider-reported usage:** control-plane probe requests and per-provider failure
  and token anomaly reports.
- **Security hardening:** a CSP or HttpOnly-cookie sessions, and MFA for operator accounts.
- **Hardware verification:** vLLM on a GPU node and the Docker worker variants.

## 11. Trust model (surfaced in the product)

On ordinary community nodes, the provider can inspect model files, process memory, and any prompt or output the workload handles. Docker isolation does not prevent this. AgentMesh will not claim otherwise. Confidential computing (TEE + attestation + key release) is a future tier and is not implemented.

The dashboard states this in the deploy form, which requires the customer to acknowledge it; on the deployment's "Try it" panel; on the landing page; and in `docs/GETTING_STARTED.md`.
