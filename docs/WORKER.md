# Running an AgentMesh Worker

A worker lets AgentMesh run open-weight models on your machine. It connects **outbound** to the control
plane over HTTPS and a WebSocket, so you do not need to open any ports on your router.

There are two ways to run it. Both use the same code (`server/node_agent`) and the same protocol.

| | Docker worker | Installable agent |
| --- | --- | --- |
| Best for | Linux servers, GPU boxes, technical operators | Ordinary computers |
| Runs models in | One container per deployment | One dedicated `ollama serve` process per deployment |
| Resource limits | Container memory/CPU/PID limits | systemd user scope (MemoryMax, CPUQuota) when available, otherwise advisory |
| Status | Implemented, unit-tested with a fake Docker client. **Not yet run against a real Docker daemon.** | Implemented and verified end to end on Linux |

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
- a private network shared only with the worker;
- a GPU only if the deployment needs one and you set `AGENTMESH_ALLOW_GPU=true`.

Known gaps: GPU detection inside the worker container is not implemented, so a Docker worker currently
advertises no GPU. Workload containers can reach the internet, because they download models themselves.

Upgrade with `docker compose -f docker-compose.worker.yml pull && ... up -d`. Workload containers keep running
across worker restarts and are re-adopted.

## 2b. Installable agent (Linux, verified)

Prerequisites: Python 3.12+ and Ollama installed (`ollama --version` must work, and it must be a complete
install able to run models).

```bash
cd server
pip install -r requirements-worker.txt
export AGENTMESH_CONTROL_PLANE_URL=https://agentmesh.example.com
export AGENTMESH_MAX_RAM_MB=8192 AGENTMESH_MAX_CPU_CORES=4
python -m node_agent hardware                 # preview what will be reported and offered
python -m node_agent enroll --token am_enroll_...
python -m node_agent run
```

No administrator rights are needed. To run it as a background service, use a systemd user unit:

```ini
# ~/.config/systemd/user/agentmesh-worker.service
[Unit]
Description=AgentMesh worker
After=network-online.target

[Service]
WorkingDirectory=%h/agentmesh/server
Environment=AGENTMESH_CONTROL_PLANE_URL=https://agentmesh.example.com
Environment=AGENTMESH_MAX_RAM_MB=8192
ExecStart=/usr/bin/python3 -m node_agent run
Restart=on-failure

[Install]
WantedBy=default.target
```

`systemctl --user enable --now agentmesh-worker`. A packaged installer for Linux and macOS is Phase 4.

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
| `AGENTMESH_PROCESS_CGROUP_LIMITS` | `true` | Use systemd user scopes for hard limits |
| `AGENTMESH_OLLAMA_IMAGE` | `ollama/ollama:0.12.3` | Docker mode image. Pin by digest in production. **This default tag has not been verified to exist.** |

## Day-to-day

- `python -m node_agent status` shows enrollment and managed workloads.
- Pause new work without stopping running deployments: `PATCH /api/v1/nodes/{id}` with
  `{"accepting_workloads": false}`.
- Stopping the worker (SIGTERM) tells the control plane right away. Agent-mode workloads stop with it and
  restart from the cached model when it returns. Docker workloads keep running.

## Uninstall

```bash
python -m node_agent uninstall --purge-models   # stops workloads, deletes credentials and model cache
```

Then revoke the node in the dashboard (`POST /api/v1/nodes/{id}/revoke`). Revoking first also works: the
worker stops all workloads and deletes its credentials when it learns it was revoked.

## Troubleshooting

| Deployment error | Meaning |
| --- | --- |
| `INSUFFICIENT_DISK` / `INSUFFICIENT_MEMORY` | The machine does not currently have the reserved resources free |
| `MODEL_PULL_FAILED` / `MODEL_PULL_STALLED` | Download failed or stopped making progress; transient registry errors are common |
| `HEALTHCHECK_FAILED` | The model downloaded but could not answer a test prompt. Check the log in `DATA_DIR/logs/` |
| `RUNTIME_START_FAILED` | Ollama (or the container) did not start |
| `PROVISION_STALLED` / `NODE_UNRESPONSIVE` | The worker stopped reporting progress or never picked up the job |

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

Commands are leased for 60 seconds and redelivered up to 3 times. The command id is the idempotency key, and
workers remember processed ids across restarts.
