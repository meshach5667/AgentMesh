# Deploying and Calling a Model

All paths are under `/api/v1`. Customer calls use a user token (`/auth/login`) or an API key.

## 1. Pick a model

```bash
curl https://agentmesh.example.com/api/v1/models
```

Each entry has `model_tag` (for example `qwen2.5:0.5b`), `license`, `download_size_mb`, `min_ram_mb`,
`min_disk_mb`, `min_cpu_cores`, and `requirements_estimated`. Requirement figures are estimates. A model in
the catalog is not guaranteed deployable: a node with enough free capacity must exist when you deploy.

## 2. Deploy

```bash
curl -X POST https://agentmesh.example.com/api/v1/deployments \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"model_id": "<id>", "config": {"num_ctx": 4096}, "idempotency_key": "my-retry-key"}'
```

`config` accepts only `num_ctx` (512 to 8192), `region`, and `require_gpu`. Anything else is rejected.
Retries with the same `idempotency_key` return the same deployment.

If no node can take it, the response is `503` with a reason breakdown, for example:

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
| `UNHEALTHY` | The node stopped reporting or the health check fails; requests get 503 |
| `STOPPING` → `STOPPED` / `CANCELLED` | Stopped after (or before) it was ready |
| `FAILED` | See `error_code` and `error_message` |

## 3. Create an API key

```bash
curl -X POST https://agentmesh.example.com/api/v1/api-keys -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" -d '{"name": "my-app", "deployment_id": "<id>"}'
```

The `key` is shown once. Omit `deployment_id` to allow all of your deployments. Revoke a key with
`DELETE /api-keys/{id}`. Deleting a deployment revokes keys scoped to it.

## 4. Call it

The endpoint speaks the Ollama API, plus Ollama's OpenAI-compatible routes:

```bash
EP=https://agentmesh.example.com/api/v1/deployments/<id>/ollama
curl $EP/api/chat -H "Authorization: Bearer am_sk_..." \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'            # streams NDJSON
curl $EP/v1/chat/completions -H "Authorization: Bearer am_sk_..." -H "Content-Type: application/json" \
  -d '{"model": "any", "messages": [{"role": "user", "content": "Hello"}]}'
```

Supported: `POST api/chat`, `POST api/generate`, `POST v1/chat/completions`, `POST v1/completions`,
`GET api/tags`, `GET v1/models`. Model management routes (`api/pull`, `api/delete`, and so on) are not exposed.

Behaviour to know:

- The `model` field is always replaced with the deployment's model. `keep_alive` is ignored, and
  `options.num_ctx` is set to the deployment's context size.
- The limits are 1 MB per request, 60 requests per minute per key, and 4 concurrent requests per deployment.
  These limits apply per control-plane process.
- Errors use `{"error": {"code": "...", "message": "..."}}`. Codes: `unauthorized`, `deployment_not_found`,
  `deployment_not_ready`, `deployment_unhealthy`, `node_unavailable`, `rate_limited`, `request_too_large`,
  `unsupported_endpoint`.
- Every response has an `X-AgentMesh-Request-Id` header.

## 5. Usage

`GET /usage/{deployment_id}` lists one record per request. Each record has the endpoint, status, outcome,
duration, response bytes, and token counts. Token counts come from the model runtime on the provider's node
(`token_source: runtime_reported`) and are not independently verified. When the runtime does not report
them they are `null`; they are never estimated. Prompts and responses are not stored or logged.

## 6. Stop and delete

`POST /deployments/{id}/stop` stops a deployment. `DELETE /deployments/{id}` stops it, hides it, and revokes
its scoped keys; usage records are kept. Capacity is released when the worker confirms cleanup, or after 5
minutes if the node is unreachable (it is told to clean up when it reconnects).

## Privacy

Models run on computers owned by community providers. A provider can see the prompts and responses their
machine processes. Do not send confidential data to community nodes.
