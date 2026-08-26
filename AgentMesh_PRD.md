# AgentMesh — Product Requirements Document (PRD)

## 1. Product Overview

**AgentMesh** is a decentralized AI compute marketplace and autonomous model deployment infrastructure.

The platform allows people and organizations to contribute compute nodes (GPUs/CPUs), define the capacity and pricing they want to offer, and earn money when their nodes are used to deploy and run AI models.

Customers can deploy AI models without manually selecting or managing physical machines. AgentMesh's AI agents discover suitable nodes, evaluate their capabilities, price, availability, reliability, and other constraints, then deploy and continuously manage workloads.

### Core thesis

> AI models should be able to autonomously find, deploy onto, and manage the infrastructure they need.

AgentMesh separates the **control plane** from the **compute plane**:

- The control plane manages identities, registry, marketplace, deployments, payments, and agents.
- Nodes provide the actual compute and run model workloads.
- AI agents autonomously make infrastructure decisions.
- Decentralization is the long-term network model; the MVP can use centralized coordination while preserving decentralized node interfaces.

---

## 2. Problem

AI model deployment currently requires users to:

- Find suitable GPU infrastructure.
- Compare GPU availability and prices.
- Provision machines.
- Configure model runtimes.
- Deploy models.
- Monitor workloads.
- Handle failures.
- Scale or migrate workloads.
- Manage infrastructure costs.

At the same time, large amounts of compute capacity are underutilized on personal machines, workstations, servers, and data-center hardware.

AgentMesh connects these two sides:

**Compute providers** contribute capacity and earn from usage.

**AI model customers** purchase compute capacity and deploy models.

**AI agents** automate infrastructure decisions and operations.

---

## 3. Goals

### MVP goals

1. Allow a computer owner to register a compute node.
2. Install and authenticate an AgentMesh Node Agent.
3. Automatically detect node hardware.
4. Maintain a centralized Node Registry.
5. Allow providers to configure offered resources and pricing.
6. Track node availability and heartbeats.
7. Allow customers to register/select AI models for deployment.
8. Allow an AgentMesh agent to select a suitable node.
9. Deploy an approved AI model on the selected node.
10. Run the model through a supported inference runtime.
11. Monitor deployment and node health.
12. Track resource usage.
13. Calculate customer charges.
14. Credit provider earnings.
15. Collect an AgentMesh platform/network fee.
16. Allow providers to view node usage and earnings.
17. Allow customers to view deployments and costs.
18. Support multiple nodes even if the initial network is operated by one person.
19. Design APIs and node protocols so external nodes can join later.
20. Keep blockchain optional for the MVP.

### Long-term goals

- Permissionless node participation.
- Decentralized node discovery.
- Cryptographic node identity.
- Trust/reputation mechanisms.
- Verifiable compute and usage.
- Automated workload migration.
- Automated scaling.
- Dynamic marketplace pricing.
- On-chain settlement.
- Staking and slashing.
- Peer-to-peer network coordination.
- Large-scale autonomous AI infrastructure.

---

## 4. Non-Goals for MVP

The MVP will not initially include:

- AgentMesh's own blockchain.
- A native token.
- Fully permissionless arbitrary code execution.
- Arbitrary Docker containers from untrusted users.
- Full decentralized consensus.
- Advanced zero-knowledge compute verification.
- Global-scale Kubernetes orchestration.
- Support for every AI model runtime.
- Complex DAO governance.

The MVP should prove the compute marketplace and autonomous deployment loop first.

---

## 5. Users

### 5.1 Compute Provider

A person or organization with available compute.

Examples:

- GPU workstation owner.
- AI developer.
- Data center.
- Research lab.
- Small server operator.
- Future cloud/GPU provider.

Provider wants to:

- Register hardware.
- Offer capacity.
- Set or accept recommended pricing.
- Control availability.
- See workloads.
- Track utilization.
- Earn money.

### 5.2 Model Customer

A developer, startup, organization, or individual who wants to run an AI model.

Customer wants to:

- Select a model.
- Specify compute requirements.
- Set budget/constraints.
- Deploy quickly.
- Access an inference endpoint.
- Monitor usage and cost.
- Stop or scale deployments.

### 5.3 AgentMesh Operator

Initially the AgentMesh team/operator.

Responsible for:

- Network operation.
- Platform policies.
- Model/runtime approval.
- Monitoring.
- Fees.
- Node onboarding controls during the MVP.

---

## 6. Core Product Concepts

### 6.1 Node

A physical or virtual machine contributing compute to AgentMesh.

A node has:

- Node identity.
- Owner.
- CPU.
- RAM.
- GPU.
- GPU count.
- VRAM.
- Storage.
- Network information.
- Region.
- Pricing.
- Availability.
- Health.
- Reputation.
- Running workloads.

### 6.2 Node Agent

Software installed on the provider's machine.

Responsibilities:

- Generate/register node identity.
- Detect hardware.
- Authenticate with AgentMesh.
- Send heartbeats.
- Report health and resource metrics.
- Receive approved deployment instructions.
- Start/stop/restart approved workloads.
- Report workload status.
- Report usage.
- Enforce resource limits.
- Never expose unrestricted host shell access to an LLM.

### 6.3 Model

An AI model that can be deployed through an approved runtime.

A model record should include:

- Name.
- Version.
- Source/reference.
- Runtime.
- Minimum VRAM.
- CPU requirements.
- RAM requirements.
- Storage requirements.
- Supported hardware.
- Deployment configuration.

### 6.4 Deployment

A running model workload on a specific node.

A deployment includes:

- Customer.
- Model.
- Node.
- Runtime.
- Configuration.
- Status.
- Start/end time.
- Resource usage.
- Cost.
- Endpoint information.

### 6.5 Marketplace

The supply and demand layer.

Providers offer compute.

Customers request compute.

AgentMesh matches workloads with suitable nodes.

---

## 7. Pricing Model

Providers do **not** pay AgentMesh to list a node.

They provide compute capacity and earn when it is used.

The provider can:

1. Accept AgentMesh's recommended price.
2. Set a custom price.
3. Eventually enable dynamic pricing.

Pricing should primarily reflect compute capability rather than simply RAM size.

Potential billable resources:

- GPU-hour.
- GPU type/performance.
- GPU VRAM.
- CPU/vCPU-hour.
- RAM GB-hour.
- Storage GB-month.
- Bandwidth.
- Optional premium for reliability/availability.

The provider controls the base price, while AgentMesh can recommend prices using market data.

The customer pays for actual usage according to the deployment's pricing and usage record.

AgentMesh takes a configurable platform/network fee.

Example:

```text
Customer compute spend: $10.00
Provider:                $9.00
AgentMesh fee:           $1.00
```

Exact percentages are not fixed by this PRD.

---

## 8. Node Lifecycle

```text
INSTALL
   ↓
IDENTIFY
   ↓
REGISTER
   ↓
HARDWARE DISCOVERY
   ↓
PRICING CONFIGURATION
   ↓
AVAILABLE
   ↓
HEARTBEAT / MONITOR
   ↓
WORKLOAD ASSIGNED
   ↓
RUNNING
   ↓
USAGE TRACKED
   ↓
SETTLEMENT
   ↓
AVAILABLE
```

If a node becomes unhealthy:

```text
RUNNING
   ↓
HEALTH FAILURE
   ↓
UNAVAILABLE
   ↓
AGENT EVALUATES WORKLOAD
   ↓
RESTART OR MIGRATE
```

---

## 9. Customer Deployment Flow

1. Customer authenticates.
2. Customer chooses a model.
3. Customer specifies requirements.
4. AgentMesh validates requirements.
5. Agent queries available nodes.
6. Agent evaluates:
   - GPU compatibility.
   - VRAM.
   - CPU/RAM.
   - Price.
   - Availability.
   - Reliability.
   - Latency/region.
7. Agent selects a node.
8. Deployment manager creates deployment.
9. Node Agent receives an authenticated deployment request.
10. Node Agent launches the approved model runtime.
11. Health check runs.
12. Deployment becomes active.
13. Customer receives inference endpoint.
14. Usage is continuously recorded.
15. Customer is charged.
16. Provider balance is credited.
17. Agent continues monitoring the workload.

---

## 10. Autonomous Agent Requirements

The AgentMesh agent must operate through controlled tools rather than unrestricted shell access.

Initial tools:

- `list_nodes`
- `get_node`
- `get_node_metrics`
- `find_capable_nodes`
- `get_model`
- `calculate_requirements`
- `deploy_model`
- `get_deployment_status`
- `restart_deployment`
- `stop_deployment`
- `scale_deployment`
- `migrate_deployment`

The agent loop:

```text
OBSERVE
   ↓
ANALYZE
   ↓
PLAN
   ↓
ACT
   ↓
VERIFY
   ↓
OBSERVE AGAIN
```

The agent should explain/log important decisions.

Example:

> Selected Node-17 because it satisfies the 24 GB VRAM requirement, has 99.5% recent availability, and offers the best estimated cost/latency combination.

---

## 11. Node Registry Requirements

The Node Registry is a core MVP service.

It must provide:

- Node registration.
- Node identity.
- Owner association.
- Hardware capabilities.
- Pricing.
- Availability.
- Health.
- Heartbeat timestamp.
- Current workload count.
- Capacity.
- Region.
- Reputation placeholder.
- Search/filter capability.

Example node state:

```text
Node ID: node_abc123
GPU: RTX 4090
VRAM: 24 GB
CPU: 16 cores
RAM: 64 GB
GPU price: $0.30/hour
Status: AVAILABLE
Utilization: 42%
Last heartbeat: 8 seconds ago
```

---

## 12. Payments Requirements

The MVP requires an internal accounting/ledger system.

### Customer wallet

Supports:

- Balance.
- Deposits.
- Compute charges.
- Refunds/credits.

### Provider earnings

Supports:

- Pending earnings.
- Available balance.
- Completed payouts.
- Usage history.

### Transactions

Every financial event must have:

- Unique transaction ID.
- Source account.
- Destination account.
- Amount.
- Currency.
- Type.
- Related deployment/order.
- Status.
- Timestamp.
- Idempotency reference.

### Important

The MVP should not assume blockchain settlement.

The payment abstraction should allow future replacement with on-chain settlement.

---

## 13. Security Requirements

Because AgentMesh runs workloads on third-party machines:

- Node identities must be cryptographically authenticated.
- Control-plane/node communication must be encrypted.
- Deployment requests must be authenticated and authorized.
- Node Agent must enforce resource limits.
- Model workloads must be sandboxed.
- Host access must be restricted.
- Secrets must never be passed directly into untrusted model containers.
- All important actions must be audited.
- Customers must not receive arbitrary host execution.
- AI agents must use explicit tools and permissions.

The MVP should support only approved model runtimes and images.

---

## 14. MVP Technology Stack

### Backend

- Python.
- FastAPI.
- SQLAlchemy.
- Pydantic.
- Alembic.

### Database

- PostgreSQL.

### Queue/state

- Redis.

### Node Agent

- Python.
- FastAPI.
- Docker SDK.
- psutil.
- NVIDIA tooling/PyTorch for GPU discovery.

### Model serving

- vLLM initially.
- Ollama may be supported for lightweight/local development.

### Frontend

- Next.js.
- TypeScript.
- Tailwind CSS.

### Monitoring

- Prometheus.
- Grafana.

### Development

- Docker.
- Docker Compose.
- uv.
- Git/GitHub.
- Pytest.

### AI

- Gemini API initially.

### Future infrastructure

- NATS.
- libp2p.
- IPFS.
- Kubernetes.
- Blockchain settlement.
- Cryptographic/verifiable compute mechanisms.

---

## 15. MVP Screens

### Provider

- Provider dashboard.
- Add/register node.
- Node details.
- Hardware.
- Pricing.
- Availability.
- Current workloads.
- Usage.
- Earnings.
- Transactions.

### Customer

- Model catalog.
- Deploy model.
- Deployment configuration.
- Active deployments.
- Inference endpoint.
- Usage.
- Cost.
- Wallet.
- Transactions.

### Operator

- Network overview.
- Node registry.
- Node health.
- Deployments.
- Model registry.
- Transactions.
- Alerts.
- Agent activity.

---

## 16. MVP Success Criteria

AgentMesh MVP is successful when:

1. A provider can install the Node Agent.
2. The node automatically detects hardware.
3. The node appears in the Node Registry.
4. Provider can configure pricing.
5. Node sends reliable heartbeats.
6. Customer can request model deployment.
7. Agent selects an eligible node.
8. Node Agent deploys an approved model.
9. Model exposes an inference API.
10. Usage is recorded.
11. Customer cost is calculated.
12. Provider earnings are calculated.
13. AgentMesh fee is recorded.
14. Provider can see earnings.
15. Customer can see costs.
16. Node failure is detected.
17. Agent can restart a failed workload.
18. A second independent node can join the network.
19. The same system works without changing the core protocol for the second node.

---

## 17. MVP Demo

The ideal first public demo:

```text
Provider
   ↓
Install Node Agent
   ↓
RTX GPU automatically detected
   ↓
Node registered
   ↓
Provider sets price
   ↓
Node becomes AVAILABLE
   ↓
Customer requests model
   ↓
Agent finds node
   ↓
Model deployed through vLLM
   ↓
Inference endpoint becomes active
   ↓
Usage is tracked
   ↓
Customer is charged
   ↓
Provider earns
   ↓
Provider sees earnings
```

Then demonstrate failure recovery:

```text
Model running
   ↓
Kill model
   ↓
Agent detects failure
   ↓
Agent restarts deployment
   ↓
Health check passes
   ↓
Model ONLINE
```

---

## 18. Future Roadmap

### V0 — Functional MVP

- Centralized control plane.
- Node Registry.
- Node Agent.
- One/two model runtimes.
- Marketplace.
- Usage accounting.
- Payments/ledger.
- AI deployment agent.

### V1 — Network

- External node onboarding.
- Node reputation.
- Dynamic pricing.
- Better scheduling.
- Automated migration.
- Multi-node deployments.
- Provider payouts.

### V2 — Decentralization

- Decentralized node discovery.
- P2P communication.
- Cryptographic node identity.
- Distributed registry.
- Verifiable usage/compute.

### V3 — Protocol

- Blockchain settlement.
- Staking.
- Slashing.
- Network incentives.
- Agent identity.
- Permissionless participation.
- AgentMesh protocol/network.

---

## 19. Product Principle

AgentMesh should not become a dashboard where humans manually manage every server.

The product should progressively automate infrastructure decisions.

The long-term experience should be:

> **Tell AgentMesh what model you want to run and what constraints matter. AgentMesh finds the infrastructure, deploys the model, operates it, monitors it, and manages the compute economy automatically.**
