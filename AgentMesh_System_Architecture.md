# AgentMesh — System Architecture

## 1. Architecture Overview

AgentMesh is designed as a decentralized compute network in which independent nodes provide compute resources and AI agents autonomously manage AI model deployments.

The initial MVP uses a centralized control plane for simplicity, but all node interactions are designed around explicit APIs and node identities so the architecture can evolve toward decentralized coordination.

```text
                         ┌─────────────────────┐
                         │      Customers      │
                         └──────────┬──────────┘
                                    │
                              Deploy Request
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────┐
│                    AGENTMESH CONTROL PLANE                    │
│                                                               │
│  ┌────────────┐   ┌────────────┐   ┌──────────────────────┐  │
│  │ API Gateway│   │ Auth       │   │ AI Agent Orchestrator │  │
│  └─────┬──────┘   └────────────┘   └───────────┬──────────┘  │
│        │                                       │              │
│  ┌─────▼──────┐   ┌────────────┐   ┌──────────▼───────────┐  │
│  │ Node       │   │ Model      │   │ Scheduler /          │  │
│  │ Registry   │   │ Registry   │   │ Placement Engine     │  │
│  └─────┬──────┘   └────────────┘   └──────────┬───────────┘  │
│        │                                       │              │
│  ┌─────▼──────┐   ┌────────────┐   ┌──────────▼───────────┐  │
│  │ Marketplace│   │ Deployment │   │ Monitoring / Events   │  │
│  │ Service    │   │ Manager    │   │                       │  │
│  └─────┬──────┘   └─────┬──────┘   └───────────────────────┘  │
│        │                │                                     │
│  ┌─────▼────────────────▼─────┐   ┌────────────────────────┐ │
│  │ Payments / Usage Ledger    │   │ PostgreSQL / Redis     │ │
│  └────────────────────────────┘   └────────────────────────┘ │
└──────────────────────┬────────────────────────────────────────┘
                       │
                 Secure Node API
                       │
          ┌────────────┼─────────────┐
          ▼            ▼             ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │   NODE 1   │ │   NODE 2   │ │   NODE N   │
   │ Node Agent │ │ Node Agent │ │ Node Agent │
   └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
         │              │              │
       Docker         Docker         Docker
         │              │              │
       vLLM           vLLM           vLLM
         │              │              │
      Models          Models          Models
```

---

## 2. Architectural Principles

### 2.1 Control Plane vs Compute Plane

The control plane coordinates the network.

The compute plane executes workloads.

The control plane should never directly run model inference.

### 2.2 Agents Decide, Node Agents Execute

AI agents make high-level decisions.

Node Agents perform authorized infrastructure operations.

```text
AI Agent:
"What should happen?"

Node Agent:
"How do I execute the approved operation safely?"
```

### 2.3 Explicit Tools

The LLM should not receive unrestricted shell access.

The AI agent operates through explicit, auditable tools.

### 2.4 Runtime Abstraction

AgentMesh should define a generic model runtime abstraction.

```text
Model
  ↓
Runtime Adapter
  ├── vLLM
  ├── Ollama
  ├── TGI
  └── TensorRT-LLM
```

The Node Agent should not be tightly coupled to one runtime.

### 2.5 Blockchain Agnostic

The MVP must not depend on blockchain.

Payment and identity interfaces should be designed so blockchain settlement can be introduced later.

---

## 3. Components

## 3.1 API Gateway

Responsibilities:

- HTTP API.
- Authentication.
- Authorization.
- Request validation.
- Rate limiting.
- Routing.
- API versioning.

Primary technology:

- FastAPI.

---

## 3.2 Authentication and Identity

Entities:

- User.
- Provider.
- Customer.
- Node.
- Agent.

Users authenticate through the platform.

Nodes use a separate machine identity.

Each node should have:

```text
node_id
public_key
credential/certificate
owner_id
status
```

Future versions can replace centralized identity with decentralized identity mechanisms.

---

## 3.3 Node Registry

The Node Registry is the authoritative MVP registry for available compute.

### Node entity

```text
Node
├── id
├── owner_id
├── public_key
├── status
├── region
├── created_at
├── last_heartbeat
└── reputation_score
```

### Hardware entity

```text
NodeHardware
├── node_id
├── cpu_model
├── cpu_cores
├── ram_bytes
├── storage_bytes
├── gpu_model
├── gpu_count
├── gpu_vram_bytes
└── capabilities
```

### Pricing entity

```text
NodePricing
├── node_id
├── gpu_hour_price
├── cpu_hour_price
├── ram_gb_hour_price
├── storage_gb_month_price
└── bandwidth_gb_price
```

### Node status

```text
REGISTERING
ONLINE
AVAILABLE
BUSY
DEGRADED
OFFLINE
SUSPENDED
```

---

## 3.4 Node Agent

The Node Agent runs on provider infrastructure.

### Responsibilities

- Node registration.
- Hardware discovery.
- Heartbeats.
- Metrics.
- Workload management.
- Runtime management.
- Usage reporting.
- Resource enforcement.
- Secure command execution.

### Internal structure

```text
node-agent/
├── api/
├── identity/
├── hardware/
├── heartbeat/
├── metrics/
├── deployment/
├── runtime/
│   ├── base.py
│   ├── vllm.py
│   └── ollama.py
├── security/
└── storage/
```

### Node Agent API

Conceptual endpoints:

```text
POST /register
POST /heartbeat
GET  /status
GET  /hardware
GET  /metrics
POST /deploy
GET  /deployments/{id}
POST /deployments/{id}/restart
POST /deployments/{id}/stop
POST /deployments/{id}/scale
```

All privileged operations require authentication and authorization.

---

## 3.5 Model Registry

Stores deployable models.

```text
Model
├── id
├── name
├── version
├── runtime
├── source
├── minimum_vram
├── minimum_ram
├── minimum_cpu
├── storage_requirement
├── supported_gpu_families
└── deployment_config
```

Only approved models/runtimes should be deployable in the MVP.

---

## 3.6 Deployment Manager

Responsible for turning a deployment request into a running workload.

### Deployment lifecycle

```text
REQUESTED
    ↓
VALIDATING
    ↓
SCHEDULING
    ↓
ASSIGNED
    ↓
DEPLOYING
    ↓
HEALTH_CHECK
    ↓
RUNNING
    ↓
STOPPING
    ↓
STOPPED
```

Failure path:

```text
DEPLOYING
    ↓
FAILED
    ↓
RETRY
    ↓
REASSIGN
```

---

## 3.7 Scheduler

The scheduler determines eligible nodes.

### Inputs

- Model requirements.
- Node hardware.
- Node availability.
- Node price.
- Current utilization.
- Reliability.
- Region.
- Latency.
- Provider policy.
- Customer constraints.

### Hard filters

Example:

```text
VRAM >= required_vram
GPU compatible = true
Node status = AVAILABLE
```

### Ranking

After filtering, candidates can be ranked by:

```text
score =
    performance_weight
  + price_weight
  + reliability_weight
  + latency_weight
  + availability_weight
```

The exact formula should evolve.

The AI agent can eventually influence ranking, but deterministic constraints should remain enforced by code.

---

## 3.8 AI Agent Orchestrator

This is the autonomous decision layer.

### Agent state

```text
current_goal
observations
available_nodes
deployments
recent_events
constraints
planned_action
```

### Agent tools

```text
list_nodes()
get_node(node_id)
get_node_metrics(node_id)
find_capable_nodes(requirements)
get_model(model_id)
deploy_model(node_id, model_id, config)
get_deployment_status(deployment_id)
restart_deployment(deployment_id)
stop_deployment(deployment_id)
scale_deployment(deployment_id, replicas)
migrate_deployment(deployment_id, node_id)
```

### Agent loop

```text
┌──────────┐
│ OBSERVE  │
└────┬─────┘
     ↓
┌──────────┐
│ ANALYZE  │
└────┬─────┘
     ↓
┌──────────┐
│  PLAN    │
└────┬─────┘
     ↓
┌──────────┐
│   ACT    │
└────┬─────┘
     ↓
┌──────────┐
│ VERIFY   │
└────┬─────┘
     │
     └──────────────→ OBSERVE
```

AI decisions should be bounded by deterministic safety policies.

---

## 3.9 Marketplace

The marketplace exposes compute supply.

### Provider flow

```text
Install Node Agent
       ↓
Register
       ↓
Hardware discovered
       ↓
Set resources/pricing
       ↓
Node AVAILABLE
```

### Customer flow

```text
Specify requirements
       ↓
Find capacity
       ↓
Agent selects node
       ↓
Create order/deployment
       ↓
Track usage
       ↓
Charge customer
```

---

## 3.10 Pricing Engine

The provider owns the base price.

AgentMesh can calculate recommendations.

### Inputs

- GPU model.
- GPU VRAM.
- GPU performance.
- CPU.
- RAM.
- Storage.
- Bandwidth.
- Node reliability.
- Current demand.
- Current supply.
- Region.

### Pricing modes

```text
PROVIDER_FIXED
AGENTMESH_RECOMMENDED
DYNAMIC
```

MVP should initially support:

```text
Provider fixed price
+
AgentMesh recommended price
```

Dynamic pricing can be added later.

---

## 3.11 Usage Metering

Usage must be measured independently of the customer's request count where possible.

Potential measurements:

```text
GPU seconds
GPU utilization
CPU seconds
RAM GB-seconds
Storage GB-time
Network bytes
Request count
Inference tokens
```

The MVP should use a clear billable unit, preferably GPU-hour for GPU workloads, with optional additional resource charges.

Usage records should be immutable after settlement or corrected through auditable adjustment records.

---

## 3.12 Payment and Ledger Service

The MVP uses an internal ledger abstraction.

### Accounts

```text
Customer Wallet
Provider Earnings Account
AgentMesh Revenue Account
```

### Transaction flow

```text
Customer balance
      ↓
Compute charge
      ↓
Usage record
      ↓
Settlement
      ├── Provider earnings
      └── AgentMesh fee
```

### Transaction states

```text
PENDING
AUTHORIZED
SETTLED
REFUNDED
FAILED
```

Every transaction must be idempotent.

### Future

Replace or augment the ledger with blockchain settlement without changing marketplace APIs.

---

## 3.13 Monitoring

### Node metrics

- CPU usage.
- RAM usage.
- GPU utilization.
- GPU memory.
- GPU temperature.
- Disk.
- Network.
- Running workloads.

### Deployment metrics

- Availability.
- Latency.
- Requests/sec.
- Errors.
- GPU utilization.
- Memory usage.

### Infrastructure

```text
Node Agent
    ↓
Prometheus metrics
    ↓
Prometheus
    ↓
Grafana
```

The control plane also stores summarized metrics required for scheduling, billing, and auditing.

---

## 4. Database Architecture

PostgreSQL is the primary persistent database.

### Core tables

```text
users
providers
customers

nodes
node_hardware
node_pricing
node_heartbeats
node_metrics

models
model_versions
model_manifests

deployments
deployment_nodes
deployment_metrics

orders
usage_records

wallets
transactions
provider_earnings
payouts

agent_tasks
agent_actions
events
audit_logs
```

### Relationships

```text
User
 ├── Provider
 │     └── Nodes
 │            ├── Hardware
 │            ├── Pricing
 │            ├── Heartbeats
 │            └── Deployments
 │
 └── Customer
       ├── Orders
       ├── Deployments
       └── Wallet

Model
 └── Deployments

Deployment
 ├── Node
 ├── Usage
 ├── Metrics
 └── Transactions
```

---

## 5. Redis Architecture

Redis is used for transient and high-frequency state.

Use cases:

- Node heartbeat state.
- Locks.
- Short-lived deployment state.
- Agent task queues.
- Rate limits.
- Caching node capabilities.
- Real-time events.

PostgreSQL remains the source of truth for persistent business data.

---

## 6. Communication

### MVP

Use HTTPS REST APIs.

```text
Control Plane
      ↕
HTTPS
      ↕
Node Agent
```

WebSockets can be used for real-time dashboard updates.

### Future

Introduce:

- NATS.
- gRPC.
- libp2p.
- Peer-to-peer node communication.

---

## 7. Security Architecture

### Node authentication

Each Node Agent generates a cryptographic identity.

```text
Node Agent
   ↓
Generate key pair
   ↓
Register public key
   ↓
Receive credential
   ↓
Authenticated communication
```

### Deployment authorization

```text
Customer request
      ↓
Control Plane authorization
      ↓
Agent decision
      ↓
Signed/authenticated deployment command
      ↓
Node Agent validates
      ↓
Approved runtime executes
```

### Workload isolation

MVP:

- Docker containers.
- CPU limits.
- Memory limits.
- GPU limits where supported.
- Restricted container privileges.
- No host Docker socket exposed to customer workloads.
- Restricted filesystem access.
- Restricted network access where appropriate.

Long-term:

- Stronger sandboxing.
- Confidential computing where useful.
- Attestation.
- Verifiable compute.

---

## 8. Deployment Architecture

Example deployment:

```text
Customer
   ↓
POST /deployments
   ↓
Control Plane
   ↓
Model Registry
   ↓
Scheduler
   ↓
AI Agent
   ↓
Node Registry
   ↓
Node selected
   ↓
Node Agent
   ↓
Docker
   ↓
vLLM
   ↓
Model
   ↓
Inference Endpoint
```

The customer should receive an AgentMesh-managed endpoint rather than direct host access.

---

## 9. Failure Handling

### Node failure

```text
Heartbeat timeout
      ↓
Node marked UNAVAILABLE
      ↓
Affected deployments identified
      ↓
Agent notified
      ↓
Find replacement node
      ↓
Deploy model
      ↓
Health check
      ↓
Route traffic
```

### Model crash

```text
Health check fails
      ↓
Restart deployment
      ↓
Verify
      ↓
If repeated:
mark unhealthy
      ↓
Migrate
```

### Payment failure

```text
Balance insufficient
      ↓
Deployment enters PAYMENT_REQUIRED
      ↓
Grace period
      ↓
Stop deployment if unresolved
```

---

## 10. Node Registry Search

The registry must support capability-based queries.

Example:

```text
find_nodes(
    gpu_vram >= 24GB,
    gpu_vendor = NVIDIA,
    status = AVAILABLE,
    region = ANY
)
```

Candidate nodes are then ranked.

Example response:

```text
Node A
RTX 4090
24GB
$0.30/hr
99.8% uptime

Node B
RTX 3090
24GB
$0.25/hr
92.0% uptime

Node C
A5000
24GB
$0.28/hr
99.5% uptime
```

The scheduler can select Node A based on a combined score.

---

## 11. Local MVP Architecture

Everything can initially run on one development machine.

```text
Docker Compose
│
├── agentmesh-api
├── agentmesh-agent
├── node-agent
├── postgres
├── redis
├── vllm
└── prometheus
```

The system should treat the local Node Agent as a normal network node.

This makes it possible to develop the distributed protocol before having external providers.

---

## 12. Multi-Node MVP

Once one node works:

```text
                 Control Plane
                       │
          ┌────────────┼────────────┐
          │            │            │
       Node 1        Node 2       Node 3
       RTX 4090      RTX 3090     A100
          │            │            │
       Node Agent   Node Agent   Node Agent
          │            │            │
       vLLM         vLLM         vLLM
```

The control plane should not need a different implementation for Node 2 or Node 3.

Every node implements the same Node Agent protocol.

---

## 13. Future Decentralized Architecture

The MVP:

```text
Central Control Plane
        │
        ├── Registry
        ├── Scheduler
        ├── Payments
        └── Agents
             │
        Independent Nodes
```

Future:

```text
              AgentMesh Network
        ┌──────────┼──────────┐
        │          │          │
      Agent      Agent      Agent
        │          │          │
      Node       Node       Node
        │          │          │
        └────── P2P Network ──┘
                   │
              Protocol Layer
                   │
              Blockchain/L2
                   │
        Identity / Settlement /
        Staking / Reputation
```

The blockchain should coordinate economic and trust functions, not execute AI inference.

---

## 14. Repository Architecture

Recommended monorepo:

```text
agentmesh/
│
├── apps/
│   ├── api/
│   ├── agent/
│   ├── node-agent/
│   └── dashboard/
│
├── packages/
│   ├── schemas/
│   ├── sdk/
│   ├── runtime-adapters/
│   └── shared/
│
├── infrastructure/
│   ├── docker/
│   ├── compose/
│   └── monitoring/
│
├── migrations/
│
├── tests/
│
├── docs/
│
└── README.md
```

---

## 15. Initial API Surface

### Authentication

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
```

### Nodes

```text
POST /api/v1/nodes/register
GET  /api/v1/nodes
GET  /api/v1/nodes/{id}
PATCH /api/v1/nodes/{id}
POST /api/v1/nodes/{id}/heartbeat
GET  /api/v1/nodes/{id}/metrics
```

### Models

```text
GET  /api/v1/models
GET  /api/v1/models/{id}
POST /api/v1/models
```

### Deployments

```text
POST /api/v1/deployments
GET  /api/v1/deployments
GET  /api/v1/deployments/{id}
POST /api/v1/deployments/{id}/stop
POST /api/v1/deployments/{id}/restart
POST /api/v1/deployments/{id}/scale
POST /api/v1/deployments/{id}/migrate
```

### Marketplace

```text
GET /api/v1/marketplace/nodes
GET /api/v1/marketplace/pricing
```

### Usage

```text
GET /api/v1/deployments/{id}/usage
GET /api/v1/usage
```

### Wallets

```text
GET /api/v1/wallet
GET /api/v1/transactions
POST /api/v1/wallet/deposit
```

### Provider earnings

```text
GET /api/v1/earnings
GET /api/v1/earnings/history
POST /api/v1/payouts
```

---

## 16. Build Sequence

### Stage 1 — Foundation

- Repository.
- FastAPI.
- PostgreSQL.
- Redis.
- Authentication.
- Database migrations.

### Stage 2 — Node Network

- Node identity.
- Node registration.
- Hardware discovery.
- Node Registry.
- Heartbeats.
- Node status.
- Provider dashboard.

### Stage 3 — Model Deployment

- Model Registry.
- Runtime abstraction.
- Docker integration.
- vLLM integration.
- Deployment Manager.
- Inference endpoint.

### Stage 4 — Marketplace

- Node pricing.
- Capability search.
- Availability.
- Scheduling.
- Customer deployment requests.

### Stage 5 — Usage and Payments

- Usage metering.
- Customer wallet.
- Internal ledger.
- Provider earnings.
- Platform fee.
- Payout workflow.

### Stage 6 — Autonomous Operations

- Agent tools.
- Agent loop.
- Health monitoring.
- Automatic restart.
- Automatic migration.
- Scheduling optimization.

### Stage 7 — Network Expansion

- External node onboarding.
- Node reputation.
- Dynamic pricing.
- Better security.
- Multi-node workloads.

### Stage 8 — Decentralization

- P2P discovery.
- Decentralized identities.
- Distributed registry.
- Verifiable compute.
- Blockchain settlement.
- Staking and slashing.

---

## 17. Architectural North Star

The final system should make the physical infrastructure almost invisible to the customer.

The customer says:

```text
Deploy Model X

Requirements:
24GB+ VRAM
<100ms latency
Budget <= $0.50/hr
High availability
```

AgentMesh should autonomously:

```text
discover
→ evaluate
→ select
→ deploy
→ monitor
→ optimize
→ scale
→ migrate
→ meter
→ settle
```

The provider sees:

```text
My Node
ONLINE

Capacity:
RTX 4090
24GB VRAM

Utilization:
71%

Earnings:
$X.XX
```

The long-term vision is:

> **A decentralized compute network where AI agents autonomously allocate, deploy, operate, and economically coordinate AI workloads across independently owned machines.**
