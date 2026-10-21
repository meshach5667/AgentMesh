# Getting Started

AgentMesh has three kinds of accounts:

- **Customers** deploy open-weight models and call them.
- **Providers** run the worker on their machines.
- **Operators** run the network.

This guide covers each role, in the dashboard and through the API. API details are in
[INFERENCE_API.md](INFERENCE_API.md), and worker details are in [WORKER.md](WORKER.md).

## What works today, and what does not

| Area | Status |
| --- | --- |
| Deploying approved models on Ollama or llama.cpp, and calling them with an OpenAI-compatible API, including streaming | Working, verified end to end on real models |
| vLLM on GPU nodes | Built and unit-tested, but not yet run on real GPU hardware |
| Automatic placement, readiness checks, moving deployments off failed nodes | Working |
| API keys, per-deployment key scoping, per-request usage metering | Working. Token counts come from the runtime and are not independently verified |
| Docker worker, and the installable agent for Linux and macOS (pause, drain, schedules, signed updates) | Working. The Docker variant has not been verified on this project's development machine |
| Customer, provider and operator dashboards | Working, using live data only |
| Prepaid billing: versioned prices, charges for READY time and tokens, Paystack top-ups, provider payouts with operator approval, reconciliation | Working in **Paystack test mode**. Verified end to end against a stand-in for Paystack's API; not yet run against Paystack itself (see [SECURITY_REVIEW.md](SECURITY_REVIEW.md)) |
| Live (real-money) payments | Not enabled: needs a live key and `PAYSTACK_ALLOW_LIVE=true`, after a review |
| Confidential computing | **Not implemented** |

**Trust model.** Deployments run on computers owned by independent providers. A provider can inspect the model
files, the process memory, and every prompt and response its node handles. Container isolation protects the
provider's machine; it does not hide customer data from the provider. Do not send confidential data to
community nodes. The dashboard shows this notice before every deployment and asks the customer to confirm it.

## Customers

1. **Sign up** at `/register` and choose *Model customer*.
2. **Pick a model** under **Models**. Each card lists:
   - the runtimes that can serve the model (green means a node offering that runtime is online now);
   - the smallest memory reservation;
   - when a deployment of the model last passed its readiness test.
3. **Deploy.** Under **Configure and deploy**, choose a runtime or *Automatic*. Then set the context window, and
   optionally a region or a GPU requirement. The form shows the resources the scheduler will reserve. Confirm
   the trust notice and press **Deploy**. If no node can take it, the form explains why for each runtime, for
   example "runtime not installed on the node" or "not enough free CPU, memory, disk or GPU memory".
4. **Watch it start.** The deployment page updates every 2 seconds while the deployment starts. It moves through
   `SCHEDULED`, `PROVISIONING` and `STARTING`, and becomes `READY` only after a real test generation succeeds.
   The page shows each event, the verified model digest, and any error code with an explanation.
5. **Try it.** On a ready deployment, **Try it** sends one real request through the gateway. That request is
   metered like any other.
6. **Create an API key** under **API Keys**. You can limit the key to one deployment and give it an expiry date.
   The key is shown once, and AgentMesh stores only a hash of it.
7. **Call it.** The deployment page has copy-paste examples for curl, the Python `openai` client, streaming,
   and, for Ollama deployments, Ollama's own API:

   ```bash
   curl https://<agentmesh>/api/v1/deployments/<id>/v1/chat/completions \
     -H "Authorization: Bearer $AGENTMESH_API_KEY" -H "Content-Type: application/json" \
     -d '{"model": "qwen2.5:0.5b", "messages": [{"role": "user", "content": "Hello"}]}'
   ```

8. **Pay for it.** Deployments are prepaid. Under **Wallet**, add funds with Paystack. In test mode, use a
   Paystack test card. The deploy form shows each runtime's hourly price, and deploying needs enough balance
   for one hour of the reservation. Charges are taken every few minutes while a deployment is READY:
   - its reserved CPU, memory and GPU memory, multiplied by READY time;
   - its input and output tokens.

   Unhealthy time is not charged. Each deployment page lists its charges, and the wallet lists them all. When
   the balance runs out, your deployments are stopped (`INSUFFICIENT_FUNDS`).
9. **Check usage** under **Usage**. It shows requests, failures, and input and output tokens per day and per
   deployment. Requests whose runtime reported no token counts are counted separately; AgentMesh never
   estimates token counts. The same data is available from `GET /api/v1/usage/summary?days=30`.
10. **Stop or delete** a deployment from its page. Deleting it also revokes any API keys limited to it.

## Providers

1. **Sign up** at `/register?role=provider`.
2. **Add a machine.** Under **Add a Machine**, create a one-time enrollment token. It is valid for 60 minutes.
   The page then shows the exact install command for the installable agent or the Docker worker, with your
   token and this network's address filled in. The worker makes outbound connections only, so you do not need
   to open any ports.
3. **Check the node.** It appears under **My Nodes** a few seconds after it enrolls. Its availability is one of:
   - **Accepting work**;
   - **Paused** (paused in AgentMesh);
   - **Unavailable** (paused, draining, or outside the schedule on the machine itself);
   - **Offline** (no heartbeats);
   - **Revoked**.

   The node page shows:
   - each runtime the worker reported, and whether resource limits are enforced or only advisory;
   - how much of the CPU, memory, disk and GPU memory you allowed is reserved by deployments;
   - the machine's last reported load.
4. **Pause or revoke.**
   - **Pause new work** stops new placements, and running deployments keep serving.
   - To also stop running deployments, run `agentmesh-worker drain` on the machine.
   - **Revoke** disables the node's credential at once. AgentMesh moves the node's deployments to other nodes
     when it can.
5. **Earnings and payouts.**
   - You are credited your share (after the platform fee) of each charge for deployments your nodes served.
     **Earnings & Payouts** lists these credits.
   - Add a bank account there; Paystack verifies it, and only its last four digits are stored. Then request
     a payout.
   - The amount is held from your balance at once. An operator approves the payout, and Paystack transfers
     it.
   - A failed or rejected payout returns the money to your balance.
   - **Served Usage** shows the requests your nodes answered.

## Operators

Operators cannot self-register. Create the first one on the server, using the same `DATABASE_URL` as the API:

```bash
cd server
python scripts/create_operator.py ops@example.com              # prompts for a password (12+ characters)
python scripts/create_operator.py lead@example.com --role admin
```

Running it for an email that already has an account promotes that account. Each use is recorded in the audit
log as `user.operator_provisioned`.

The operator dashboard (`/operator`) has these pages:

| Page | Shows | API |
| --- | --- | --- |
| Overview | Nodes and deployments by status, deployable models, last-24-hour requests and tokens, ledger totals, and a warning for nodes whose heartbeats are overdue | `GET /admin/overview` |
| All Nodes | Every node with its owner. Pause, resume, revoke | `GET /admin/nodes`, `PATCH /nodes/{id}`, `POST /nodes/{id}/revoke` |
| All Deployments | Every deployment with its customer, error code, and placement attempts. Stop | `GET /admin/deployments`, `POST /deployments/{id}/stop` |
| Model Catalog | Approved and unapproved models, and their artifacts. Approve, or enable and disable artifacts | `GET /admin/models`, `POST /models/{id}/approval`, `PATCH /models/{id}/artifacts/{id}` |
| Network Usage | Requests and tokens across the network | `GET /usage/summary?scope=network` |
| Pricing | Publish an immutable price version, effective now or later | `GET/POST /admin/pricing` |
| Payouts | Approve (sends the Paystack transfer) or reject (returns the funds) | `GET /admin/payouts`, `POST /admin/payouts/{id}/approve or reject` |
| Reconciliation | Ledger invariants and open items; check them with Paystack | `GET /admin/reconciliation`, `POST /admin/reconciliation/run` |
| Ledger | Recent ledger entries | `GET /admin/transactions` |
| Audit Log | Security-relevant actions, searchable by action and resource | `GET /admin/audit-logs` |

Adding a new artifact, which needs a pinned source, is done through `POST /models/{id}/artifacts`. There is no
dashboard form for it yet.

## Public network figures

`GET /api/v1/stats/public` needs no authentication. The landing page uses it. It returns counts only:

- nodes online, and GPU nodes online;
- runtimes online;
- deployable models;
- deployments serving.

It also returns flags showing which product features are enabled. It never returns node names, owners,
locations, or hardware.
