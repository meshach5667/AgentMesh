# Running an AgentMesh Worker

A worker lets AgentMesh run open-weight models on your machine. It connects **outbound** to the control
plane over HTTPS and a WebSocket, so you do not need to open any ports on your router.

There are two ways to run it. Both use the same code (`server/node_agent`) and the same protocol.

| | Docker worker | Installable agent |
| --- | --- | --- |
| Best for | Linux servers, GPU boxes, technical operators | Ordinary computers |
| Runs models in | One container per deployment | One dedicated `ollama serve` process per deployment |
| Resource limits | Container memory/CPU/PID limits | systemd user scope (MemoryMax, CPUQuota) when available, otherwise advisory |
| Status | Implemented, unit-tested with a fake Docker client. **Not yet run against a real Docker daemon.** | Installer, service, pause/drain, signed updates, and real inference verified on Linux. macOS service files are generated and unit-tested but not run on a Mac |

## What AgentMesh will and will not do on your machine

- It only uses the CPU, memory, disk, and GPU you allocate. Defaults are half your CPU cores and RAM, at most
  20 GB of disk, and **no GPU**.
- It never touches your own Ollama install. It does not use port 11434, `~/.ollama`, or your existing models.
  Workloads use their own port, their own model directory, and their own process or container.
- It never runs commands sent by customers. The control plane can only ask for "deploy model X from the
  approved catalog with these limits" or "stop deployment Y". The worker validates both.
- It does not upload files, browser data, or credentials. Hardware reports contain CPU model, core count,
  RAM, free disk, OS, architecture, and GPU model and VRAM.

**Trust model.** You, as the machine owner, can inspect the model files, the running process, and the
prompts and responses it handles. Containers do not prevent this. Customers are told not to send sensitive
data to community nodes.

## 1. Get an enrollment token

In the provider dashboard (or with the API), create a one-time enrollment token. It expires after 60 minutes
and can be used once.

```bash
curl -X POST https://agentmesh.example.com/api/v1/nodes/enrollment-tokens \
  -H "Authorization: Bearer $PROVIDER_JWT" -H "Content-Type: application/json" -d '{"name": "my-box"}'
```

## 2a. Docker worker

Prerequisites: Docker Engine 24+, and for GPUs the NVIDIA Container Toolkit.

```bash
export AGENTMESH_CONTROL_PLANE_URL=https://agentmesh.example.com
export AGENTMESH_ENROLLMENT_TOKEN=am_enroll_...
export DOCKER_GID=$(getent group docker | cut -d: -f3)
export AGENTMESH_MAX_RAM_MB=8192 AGENTMESH_MAX_CPU_CORES=4 AGENTMESH_MAX_DISK_MB=30000
docker compose -f docker-compose.worker.yml up -d
docker compose -f docker-compose.worker.yml logs -f worker
```

The worker needs the Docker socket to create workload containers. **Access to the Docker socket is
equivalent to root on the host.** Prefer rootless Docker, and run the worker on a machine dedicated to this
purpose. Workload containers never receive the socket. Each one runs with:

- memory and swap limits, a CPU quota, and a PID limit;
- all Linux capabilities dropped, `no-new-privileges`, and a read-only root filesystem;
- no host bind mounts, only the `agentmesh-models` volume;
- a private, internal network shared only with the worker, with **no route to the internet once the model is
  downloaded** (the container joins `agentmesh-egress` for the download only and is disconnected before it
  serves anything);
- a GPU only if the deployment needs one and you set `AGENTMESH_ALLOW_GPU=true`.

Known gap: GPU detection inside the worker container is not implemented, so a Docker worker currently
advertises no GPU.

Upgrade with `docker compose -f docker-compose.worker.yml pull && ... up -d`. Workload containers keep running
across worker restarts and are re-adopted.

## 2b. Installable agent (Linux and macOS, no admin rights)

Prerequisites: Python 3.11+ (with `venv`) and Ollama installed from https://ollama.com/download. The installer
uses your Ollama binary to start AgentMesh's own isolated instances. It never installs, updates, configures, or
connects to your Ollama service, port 11434, or your models.

```bash
cd server
python scripts/build_worker_wheel.py            # or use a wheel published by your operator
./packaging/install.sh --control-plane https://agentmesh.example.com --token am_enroll_... \
    --max-ram-mb 8192 --max-cpu 4 --max-disk-mb 30000 \
    --schedule "mon-fri 18:00-08:00, weekends 00:00-24:00" --outside-schedule pause \
    --update-public-key <base64 key from your operator>
```

The installer:

1. checks your OS, Python, and Ollama;
2. creates a private Python environment in `~/.local/share/agentmesh/venv-agentmesh-worker`;
3. writes `~/.config/agentmesh/agentmesh-worker.env` with permissions 0600;
4. enrolls the machine with the one-time token;
5. starts a per-user background service. On Linux that's a systemd user unit; on macOS it's a launchd agent.

Add `--linger` on Linux to keep the worker running while you are logged out. Add `--no-service` to run
`agentmesh-worker run` under your own supervisor instead.

On Linux, each model runs in its own systemd scope with hard memory and CPU limits. On macOS the limits are
advisory: the scheduler never reserves more than you allow, but the OS does not enforce it.

### Everyday commands

Run these with `AGENTMESH_CONFIG_FILE` pointing at your config file, or from the installer's environment.

| Command | What it does |
| --- | --- |
| `agentmesh-worker status` | Enrollment, connection, local pause/drain state, schedule, running workloads |
| `agentmesh-worker doctor [--deep]` | Checks platform, Python, config, control plane, credential, Ollama, cgroup limits, Docker access, disk, memory, GPUs, and schedule, and prints a fix for each problem. `--deep` also starts a throwaway Ollama instance |
| `agentmesh-worker pause` | Stop taking new deployments. Running ones keep serving |
| `agentmesh-worker drain` | Stop taking new deployments and stop running ones. AgentMesh moves them to other nodes when possible |
| `agentmesh-worker resume` | Take work again (within your schedule) |
| `agentmesh-worker hardware` | What is reported and what is offered |
| `agentmesh-worker update [--check]` | Install a signed update (see below) |

### Availability schedule

`AGENTMESH_AVAILABILITY_SCHEDULE` limits when your machine takes work, in local time. Examples:
`"mon-fri 18:00-08:00"`, `"weekends 00:00-24:00"`, `"daily 22:00-07:00"`. A window that ends before it starts
runs past midnight.

Outside the schedule, `AGENTMESH_OUTSIDE_SCHEDULE=pause` (the default) keeps running deployments but takes no
new ones. `drain` stops them so they move elsewhere.

### Signed updates

Your operator signs each release with an offline key. The installer pins the matching public key
(`--update-public-key`). Only releases signed by that key are accepted, so even a compromised control plane
cannot push code to your machine.

`agentmesh-worker update`:

1. verifies the signature;
2. refuses downgrades;
3. checks the wheel's SHA-256;
4. installs the new version into the worker's own environment;
5. confirms it starts, and rolls back to the previous wheel if it doesn't.

Restart the service afterwards. With `AGENTMESH_AUTO_UPDATE=true`, the worker does this by itself, but only
while it has no workloads.

Operators publish releases with `scripts/sign_worker_release.py` and point `WORKER_RELEASE_DIR` at the output.

## Model runtimes

A worker offers every runtime enabled in `AGENTMESH_ENABLED_RUNTIMES` (default: all three). Each one reports
honestly whether it can run on this machine, and AgentMesh only schedules a runtime onto nodes where it is
available. `agentmesh-worker status` and the enrollment output list them.

| Runtime | Installable agent | Docker worker | Needs |
| --- | --- | --- | --- |
| Ollama | `ollama serve` per deployment | `ollama/ollama` container | Ollama installed (agent) |
| llama.cpp | `llama-server` per deployment | Not yet | A `llama-server` binary from a llama.cpp release (`AGENTMESH_LLAMA_SERVER_BINARY`) |
| vLLM | `vllm serve` per deployment | `vllm/vllm-openai` container | An NVIDIA GPU and `AGENTMESH_ALLOW_GPU=true`; `vllm` installed (agent) |

Model files:

- **Hugging Face only.** llama.cpp and vLLM download weights only from `huggingface.co` and its file hosts
  (`AGENTMESH_ALLOWED_MODEL_HOSTS`). Every redirect is checked against that list.
- **Pinned and verified.** Revisions are pinned commits. llama.cpp GGUF files are checked against their
  SHA-256 before loading and cached by hash in the data directory.
- **No gated models.** Gated or private models are refused; no access tokens are ever placed on your machine.
- **Isolated like Ollama.** Each runtime instance runs on a random loopback port in its own process group,
  with the same systemd-scope memory and CPU limits.

vLLM has been implemented and unit-tested, but **has not yet run on real GPU hardware**. The default
`AGENTMESH_VLLM_IMAGE` tag is unverified; pin an image digest you have tested.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AGENTMESH_CONTROL_PLANE_URL` | `http://localhost:8000` | Must be `https://` unless the host is loopback |
| `AGENTMESH_ALLOW_INSECURE_CONTROL_PLANE` | `false` | Allow plain HTTP to a non-loopback host (private networks only) |
| `AGENTMESH_DATA_DIR` | `~/.agentmesh/worker` | Credentials (0600), workload state, model cache, logs |
| `AGENTMESH_MODE` | `agent` | `agent` or `docker` |
| `AGENTMESH_MAX_CPU_CORES` / `_RAM_MB` / `_DISK_MB` | half CPU and RAM, at most 20 GB disk | Capacity offered |
| `AGENTMESH_ALLOW_GPU` / `AGENTMESH_MAX_VRAM_MB` | `false` / all | GPU sharing |
| `AGENTMESH_OLLAMA_BINARY` | `ollama` | Agent mode runtime binary |
| `AGENTMESH_ENABLED_RUNTIMES` | `ollama,llamacpp,vllm` | Runtimes this worker offers |
| `AGENTMESH_LLAMA_SERVER_BINARY` / `AGENTMESH_VLLM_BINARY` | `llama-server` / `vllm` | Agent mode binaries for llama.cpp and vLLM |
| `AGENTMESH_VLLM_IMAGE` | `vllm/vllm-openai:v0.10.1` | Docker mode vLLM image (unverified default; pin a digest) |
| `AGENTMESH_ALLOWED_MODEL_HOSTS` | `huggingface.co,*.huggingface.co,*.hf.co` | Hosts model weights may be downloaded from |
| `AGENTMESH_PROCESS_CGROUP_LIMITS` | `true` | Use systemd user scopes for hard limits |
| `AGENTMESH_WORKLOAD_NETWORK` / `AGENTMESH_EGRESS_NETWORK` | unset | Docker mode: internal serving network and download-only egress network (set by the Compose file) |
| `AGENTMESH_PULL_ATTEMPTS` | `3` | Retries for model downloads that fail transiently (registry 5xx, timeouts) |
| `AGENTMESH_AVAILABILITY_SCHEDULE` / `AGENTMESH_OUTSIDE_SCHEDULE` | always / `pause` | When the machine takes work, and what happens outside that window |
| `AGENTMESH_UPDATE_PUBLIC_KEY` / `AGENTMESH_AUTO_UPDATE` | unset / `false` | Pinned release key (updates are refused without it); apply updates automatically when idle |
| `AGENTMESH_CONFIG_FILE` | `~/.config/agentmesh/worker.env` | Config file; environment variables override it |
| `AGENTMESH_OLLAMA_IMAGE` | `ollama/ollama:0.12.3` | Docker mode image. Pin by digest in production. **This default tag has not been verified to exist.** |

## Pausing from the dashboard and stopping the worker

- The dashboard pause (`PATCH /api/v1/nodes/{id}` with `{"accepting_workloads": false}`) and the local
  `agentmesh-worker pause` are independent. The node takes new work only when neither is paused.
- Stopping the worker (SIGTERM, or stopping the service) tells the control plane right away. Agent-mode
  workloads stop with it and restart from the cached model when it returns. Docker workloads keep running.

## Uninstall

Installable agent:

```bash
./packaging/uninstall.sh --purge-models
```

This stops the service and every managed workload, deletes the credential, config, private environment, and
(with `--purge-models`) downloaded models. It leaves your Ollama untouched. Docker worker:
`docker compose -f docker-compose.worker.yml down -v`.

Then revoke the node in the dashboard (`POST /api/v1/nodes/{id}/revoke`). Revoking first also works: the
worker stops all workloads and deletes its credentials when it learns it was revoked.

## Troubleshooting

Start with `agentmesh-worker doctor`. It prints a concrete fix for each problem it finds, such as missing
Docker group membership, no reachable control plane, a revoked credential, or too little free memory.

| Deployment error | Meaning |
| --- | --- |
| `INSUFFICIENT_DISK` / `INSUFFICIENT_MEMORY` | The machine does not currently have the reserved resources free |
| `MODEL_PULL_FAILED` / `MODEL_PULL_STALLED` | Download failed. Transient errors are retried 3 times on the node first; a model that does not exist fails at once |
| `MODEL_INTEGRITY_FAILED` | The downloaded file did not match the catalog's SHA-256 or size; it was deleted |
| `MODEL_ACCESS_DENIED` | The model is gated or private on Hugging Face; AgentMesh does not use access tokens |
| `MODEL_SOURCE_REJECTED` | A download or redirect pointed outside the allowed hosts |
| `RUNTIME_UNAVAILABLE` / `WORKER_ERROR` | The runtime is not available on this node, or an unexpected worker error; the deployment moves elsewhere if possible |
| `HEALTHCHECK_FAILED` | The model downloaded but could not answer a test prompt. Check the log in `DATA_DIR/logs/` |
| `RUNTIME_START_FAILED` | Ollama (or the container) did not start |
| `NODE_UNAVAILABLE` | You paused or drained the machine, or its schedule ended. The deployment moves to another node if one is available |
| `PROVISION_STALLED` / `NODE_UNRESPONSIVE` / `NODE_OFFLINE` | The worker stopped reporting progress, never picked up the job, or went offline. The deployment is moved to another node if one is available |

## Worker protocol v1 (for implementers)

All requests carry `X-AgentMesh-Protocol: 1`. After enrollment they also carry
`Authorization: Bearer <node credential>` and `X-AgentMesh-Node-Id`. Unknown fields are rejected, and bodies
are limited to 256 KB.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/worker/enroll` | Exchange a one-time token, hardware, allocation, and runtimes for a node credential |
| `POST /api/v1/worker/heartbeat` | Liveness, allocation, metrics, workload health. Response lists workloads to stop |
| `POST /api/v1/worker/commands/poll` | Long-poll (up to 25 s) for leased `DEPLOY`/`STOP` commands |
| `POST /api/v1/worker/commands/{id}/ack` | `accepted` / `succeeded` / `failed`. Idempotent |
| `POST /api/v1/worker/deployments/{id}/status` | `PROVISIONING`, `STARTING`, `READY`, `FAILED`, `STOPPED`, with an optional message, error code, and digest |
| `POST /api/v1/worker/disconnect` | Graceful shutdown |
| `WS /api/v1/worker/tunnel` | Inference frames: `request`, `cancel` (from the server); `response_start`, `chunk`, `response_end`, `error` (from the worker) |

Command types are `DEPLOY`, `STOP`, and `RESTART` (stop the local runtime and deploy again from the cache).
Commands are leased for 60 seconds and redelivered up to 3 times. The command id is the idempotency key, and
workers remember processed ids across restarts.
