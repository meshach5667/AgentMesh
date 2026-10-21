# Deploying and Calling a Model

All paths are under `/api/v1`. Account calls use a session token from `/auth/login`; calls to a deployment use an
API key (or a session token). The same material, with SDK examples, is in the dashboard docs at
https://agent-mesh-ten.vercel.app/docs/api.

## 1. Pick a model and runtime

```bash
curl https://agentmesh-riuz.onrender.com/api/v1/models
```

Each model lists its `artifacts`: one per runtime that can serve it. Every artifact pins its source, an Ollama
tag or a Hugging Face commit, and records its own resource needs (`min_ram_mb`, `min_disk_mb`, `min_vram_mb`,
`gpu_required`). The figures are estimates. `last_ready_at` shows when a deployment of that artifact last
passed its readiness test. Appearing in the catalog does not guarantee a node with enough free capacity
exists.

| Runtime | Serves | Hardware | APIs through AgentMesh | Notes |
| --- | --- | --- | --- | --- |
| `ollama` | Ollama registry tags | CPU or GPU | `/ollama/api/chat`, `/ollama/api/generate`, and `/v1/*` | Widest node availability |
| `llamacpp` | One GGUF file from Hugging Face, pinned to a commit and verified by SHA-256 | CPU (GPU offload where the node's build supports it) | `/v1/chat/completions`, `/v1/completions`, `/v1/models` | Smaller reservations for the same model |
| `vllm` | A full Hugging Face repository at a pinned commit | **GPU required** | `/v1/chat/completions`, `/v1/completions`, `/v1/models` | Highest throughput; **not yet verified on real hardware** |

Gated or private Hugging Face models are not supported: AgentMesh does not send access tokens to provider
machines.

## 2. Deploy

```bash
curl -X POST https://agentmesh-riuz.onrender.com/api/v1/deployments \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"model_id": "<id>", "config": {"num_ctx": 4096}, "idempotency_key": "my-retry-key"}'
```

Add `"runtime": "llamacpp"` (or `ollama`, `vllm`) to choose a runtime. If you omit it, AgentMesh tries
the model's runtimes in the order `ollama`, `llamacpp`, `vllm` and uses the first that fits on a node.

`config` accepts only `num_ctx` (512 to 8192), `region`, and `require_gpu`. Anything else is rejected.
Retries with the same `idempotency_key` return the same deployment.

If no node can take it, the response is `503` with a reason breakdown. `by_runtime` explains each runtime
separately. For example:

```json
{"detail": {"code": "no_eligible_node", "reasons": {"insufficient_capacity": 2, "provider_unavailable": 1}}}
```

Poll `GET /deployments/{id}` (or `GET /deployments/{id}/events` for progress) until `status` is `READY`.

| Status | Meaning |
| --- | --- |
| `SCHEDULED` | Capacity reserved on a node |
| `PROVISIONING` | Runtime starting and model downloading |
| `STARTING` | Model loading; a test generation is run |
| `READY` | The test generation succeeded; `endpoint` is set |
| `UNHEALTHY` | The node stopped reporting or the health check fails; requests get 503. If it does not recover within 3 minutes, the deployment moves to another node |
| `STOPPING` → `STOPPED` / `CANCELLED` | Stopped after (or before) it was ready |
| `FAILED` | See `error_code` and `error_message` |

### If a node fails

When a node goes offline, is revoked, or runs out of memory or disk, the deployment moves to another
eligible node automatically. Its id, endpoint, and API keys stay the same, so your application needs no
changes. While it moves, requests return `503` (`node_unavailable` or `deployment_unhealthy`) or `409`
(`deployment_not_ready`); retry with backoff. A deployment is tried on at most 3 nodes (`schedule_attempts`
in the deployment). Model problems, such as a model that cannot answer a test prompt, are not retried
elsewhere and end in `FAILED`.

To restart a serving deployment on its current node (for example after it misbehaves), call
`POST /deployments/{id}/restart`. It goes back to `PROVISIONING` and becomes `READY` again from the cached
model.

## 3. Create an API key

```bash
curl -X POST https://agentmesh-riuz.onrender.com/api/v1/api-keys -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" -d '{"name": "my-app", "deployment_id": "<id>"}'
```

The `key` is shown once. Omit `deployment_id` to allow all of your deployments. Revoke a key with
`DELETE /api-keys/{id}`. Deleting a deployment revokes keys scoped to it.

## 4. Call it

Every deployment has `openai_base_url` (`.../deployments/<id>/v1`), which works for every runtime:

```bash
BASE=https://agentmesh-riuz.onrender.com/api/v1/deployments/<id>/v1
curl $BASE/chat/completions -H "Authorization: Bearer am_sk_..." -H "Content-Type: application/json" \
  -d '{"model": "any", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

Ollama deployments also expose Ollama's own API at `endpoint` (`.../deployments/<id>/ollama`):

```bash
curl https://agentmesh-riuz.onrender.com/api/v1/deployments/<id>/ollama/api/chat -H "Authorization: Bearer am_sk_..." \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'            # streams NDJSON
```

Calling an `/ollama/...` route on a llama.cpp or vLLM deployment returns `404` and points you to `/v1`.
Model management routes (`api/pull`, `api/delete`, and so on) are never exposed.

Behaviour to know:

- The `model` field is always replaced with the deployment's model. For Ollama, `keep_alive` is ignored and
  `options.num_ctx` is set to the deployment's context size.
- Streaming `/v1` requests get `stream_options.include_usage` added, unless you set it, so token counts can be
  metered. The final stream chunk then carries a `usage` object.
- The limits are 1 MB per request, 60 requests per minute per key, and 4 concurrent requests per deployment.
  These limits apply per control-plane process.
- Errors use `{"error": {"code": "...", "message": "..."}}`. Codes: `unauthorized` (401), `deployment_not_found`
  (404, also for a key scoped to another deployment), `deployment_not_ready` (409), `deployment_unhealthy` (503),
  `node_unavailable` (502/503), `timeout` (504), `rate_limited` (429, with `Retry-After`),
  `too_many_concurrent_requests` (429), `request_too_large` (413), `unsupported_endpoint` (404).
- API keys authenticate only the gateway routes above. Account endpoints (`/deployments`, `/api-keys`, billing)
  need the session token from `/auth/login`. The gateway also accepts a session token.
- Every response has an `X-Request-ID` header (generated by AgentMesh). Quote it when reporting a problem:
  operators can trace it through the gateway, worker logs, usage records, and the audit log.

## 5. Usage

`GET /usage/{deployment_id}` lists one record per request. Each record has the endpoint, status, outcome,
duration, response bytes, and token counts. Token counts come from the model runtime on the provider's node
(`token_source: runtime_reported`) and are not independently verified. When the runtime does not report
them they are `null`; they are never estimated. Prompts and responses are not stored or logged. The newest 200
records are returned by default (`?limit=` up to 1000).

`GET /usage/summary?days=30` aggregates the last 1 to 90 days, per day and per deployment:

- `requests`, `succeeded` and `failed`;
- `input_tokens` and `output_tokens`;
- `requests_without_token_counts`.

Customers see their own deployments, and providers see the requests their nodes served. Operators can pass
`scope=network`.

Charges are separate from usage. `GET /billing/charges?deployment_id=...` lists what each billing window cost.
`GET /billing/pricing` returns the price list in force.

Deployments are prepaid. `POST /deployments` returns `402` with
`{"detail": {"code": "insufficient_balance", "required": ..., "balance": ...}}` when the wallet cannot cover
`BILLING_MIN_PREPAID_HOURS` of the reservation. Top up with `POST /payments/topups` (Paystack checkout); see
[GETTING_STARTED.md](GETTING_STARTED.md).

## 6. Stop and delete

`POST /deployments/{id}/stop` stops a deployment. `DELETE /deployments/{id}` stops it, hides it, and revokes
its scoped keys; usage records are kept. Capacity is released when the worker confirms cleanup, or after 5
minutes if the node is unreachable (it is told to clean up when it reconnects).

## Privacy

Models run on computers owned by community providers. A provider can see the prompts and responses their
machine processes. Do not send confidential data to community nodes.
