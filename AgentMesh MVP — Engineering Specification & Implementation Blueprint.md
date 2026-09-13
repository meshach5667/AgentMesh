# AgentMesh MVP
## Engineering Specification, Architecture & Implementation Blueprint

**Product:** AgentMesh  
**Version:** MVP v0.1  
**Core concept:** AI-agent orchestration over distributed compute  
**Primary goal:** Securely route AI workloads to independent compute nodes without requiring developers to manage infrastructure.



# 1. Product Definition

AgentMesh is a distributed AI infrastructure platform.

Developers submit AI workloads through an API or SDK.

AgentMesh:

1. authenticates the developer
2. validates the workload
3. determines required compute capabilities
4. discovers eligible compute nodes
5. evaluates node health/capability
6. selects a node
7. dispatches the workload
8. executes it inside an isolated runtime
9. monitors execution
10. returns the result
11. records usage
12. calculates cost
13. updates the provider/developer ledger

The important abstraction is:

```text
Developer
    |
    v
AgentMesh API
    |
    v
Scheduler
    |
    v
Secure Workload Dispatcher
    |
    +----------+----------+
    |          |          |
    v          v          v
 Node A     Node B      Node C
    |          |          |
    v          v          v
 Model      Model       Model
    |          |          |
    +----------+----------+
               |
               v
            Result
```

The developer should **not need to know which physical machine executes the workload**.

---

# 2. MVP Scope

The first version should support only:

### Developer side

- account creation/login
- API keys
- project management
- workload submission
- workload status
- result retrieval
- usage statistics
- basic balance/credit system

### Node-provider side

- node registration
- node authentication
- hardware discovery
- model/runtime registration
- health reporting
- workload execution
- resource monitoring
- provider usage/reward statistics

### AgentMesh platform

- API gateway
- authentication
- node registry
- scheduler
- workload queue
- workload dispatcher
- model registry
- usage metering
- billing ledger
- node reputation
- security controls
- audit logs
- monitoring

### Explicitly NOT MVP

Do not build:

- token
- DAO
- blockchain
- custom consensus
- decentralized identity protocol
- complex agent-to-agent protocol
- global GPU marketplace
- Kubernetes federation
- custom container runtime
- zero-knowledge verification
- TEE-based verification as a requirement
- automatic model training
- arbitrary code execution for customers

Those can come later.

---

# 3. Core MVP Use Case

A developer should be able to do:

```text
POST /v1/inference
```

with something conceptually like:

```json
{
  "model": "qwen2.5-7b",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": "Explain distributed systems."
      }
    ]
  },
  "requirements": {
    "min_vram_gb": 12,
    "max_latency_ms": 2000
  }
}
```

AgentMesh then performs:

```text
Request
   |
   v
Authenticate
   |
   v
Validate
   |
   v
Create Workload
   |
   v
Scheduler
   |
   v
Find eligible nodes
   |
   v
Select node
   |
   v
Dispatch
   |
   v
Execute
   |
   v
Collect result
   |
   v
Meter usage
   |
   v
Return result
```

---

# 4. Recommended Technology Stack

## Control Plane

Use:

- Next.js for dashboard
- Node.js backend/API
- PostgreSQL
- Redis
- BullMQ or equivalent queue
- Docker
- REST API
- WebSocket/SSE for live workload status

You can use FastAPI instead of Node if you want Python throughout the infrastructure layer, but for the MVP I would keep the control plane in one ecosystem.

## Node Agent

Use:

- Python or Go
- Docker Engine
- NVIDIA Container Toolkit for NVIDIA GPUs
- gRPC or HTTPS for control communication

I would personally use **Go for the node agent** eventually.

For your first prototype, Python is perfectly acceptable.

## AI Runtime

Do not build your own inference engine.

Support existing runtimes such as:

```text
vLLM
Ollama
llama.cpp
```

Start with **one**.

For a serious GPU-oriented MVP, vLLM is the stronger direction.

---

# 5. Monorepo Structure

Use a monorepo from day one.

```text
agentmesh/
│
├── apps/
│   ├── dashboard/
│   └── api/
│
├── services/
│   ├── scheduler/
│   ├── dispatcher/
│   ├── billing/
│   └── registry/
│
├── node/
│   └── agent/
│
├── packages/
│   ├── shared/
│   ├── protocol/
│   ├── auth/
│   └── validation/
│
├── infrastructure/
│   ├── docker/
│   ├── postgres/
│   ├── redis/
│   └── monitoring/
│
├── docs/
│   ├── architecture.md
│   ├── security.md
│   ├── node-protocol.md
│   ├── api.md
│   └── threat-model.md
│
├── tests/
│
├── docker-compose.yml
├── .env.example
└── README.md
```

Do not put everything inside one giant Next.js application.

---

# 6. System Components

## 6.1 API Gateway

Responsible for:

- authentication
- authorization
- rate limiting
- request validation
- API versioning
- request IDs
- audit logging

Example:

```text
Client
  |
  v
API Gateway
  |
  +--> Auth
  |
  +--> Rate Limiter
  |
  +--> Request Validation
  |
  v
Internal Services
```

Every request should receive a unique:

```text
request_id
```

Example:

```text
req_01JABC123
```

This ID must appear in logs throughout the system.

---

# 7. Authentication

Use two different identity systems.

## Developers

Use:

```text
Account
   |
   +-- Project
          |
          +-- API Key
```

Never use a user's password as an API credential.

API keys should look like:

```text
am_live_xxxxxxxxx
```

Store only a hash of the secret.

Example database:

```text
api_keys

id
project_id
key_hash
key_prefix
created_at
last_used_at
expires_at
revoked_at
```

If a key is leaked:

```text
revoke key
create new key
```

---

# 8. Node Authentication

Nodes require a separate authentication mechanism.

Do not let nodes authenticate using normal user API keys.

Node registration:

```text
Provider
   |
   v
Register Node
   |
   v
AgentMesh issues node credential
   |
   v
Node establishes authenticated connection
```

For the MVP:

- short-lived access tokens
- refresh/rotation mechanism
- TLS
- node ID
- credential revocation

Later:

- mTLS
- hardware-backed identity
- remote attestation

NIST's Zero Trust model is a good architectural principle here: do not automatically trust a node because it is “inside” the AgentMesh network or because it registered successfully. Authentication and authorization should be explicit for users, devices and resources.

---

# 9. Node Registry

The registry stores information about every node.

Example:

```text
nodes

id
provider_id
status
hostname
region
country
cpu_cores
ram_gb
gpu_model
gpu_count
vram_gb
runtime
models
network_latency
last_heartbeat
reputation_score
created_at
```

Possible states:

```text
PENDING
ONLINE
BUSY
OFFLINE
SUSPENDED
BANNED
```

---

# 10. Node Registration

A node should never simply send:

```text
"I have an RTX 4090."
```

and be trusted.

The node agent should collect hardware information locally.

Example:

```text
GPU:
NVIDIA RTX 4090

VRAM:
24 GB

CUDA:
12.x

CPU:
16 cores

RAM:
64 GB

Disk:
1 TB

Runtime:
Docker

Models:
Qwen
Llama
```

The control plane records the information.

But remember:

> Hardware claims from an untrusted machine are claims, not proof.

That distinction is important.

---

# 11. Node Heartbeat

Every node periodically sends:

```text
POST /internal/nodes/{id}/heartbeat
```

Example:

```json
{
  "status": "READY",
  "cpu_percent": 31,
  "memory_percent": 48,
  "gpu_percent": 22,
  "gpu_memory_used": 8.4,
  "active_jobs": 1
}
```

If the node stops sending heartbeats:

```text
ONLINE
   |
heartbeat timeout
   |
SUSPECTED
   |
timeout continues
   |
OFFLINE
```

Never schedule new workloads to an unhealthy node.

---

# 12. Node Agent

The node agent is one of the most important components.

It should:

- authenticate with AgentMesh
- report hardware
- maintain heartbeat
- receive workload assignments
- pull approved model/runtime
- execute workloads
- enforce resource limits
- monitor execution
- return output
- clean up workload
- report usage

Architecture:

```text
                Node Agent
                    |
        +-----------+-----------+
        |           |           |
     Control     Runtime     Monitor
     Client      Manager      |
        |           |          |
        v           v          v
   AgentMesh      Docker    GPU/CPU/RAM
```

---

# 13. CRITICAL SECURITY RULE

## Never execute arbitrary customer code directly on a provider machine.

This would be one of the most dangerous mistakes you could make.

Bad:

```text
Developer
   |
   v
"run this Python script"
   |
   v
Provider machine
```

A malicious customer could attempt:

```text
filesystem access
credential theft
network scanning
container escape
cryptomining
lateral movement
```

Instead, the MVP should initially support **controlled inference workloads only**.

For example:

```text
MODEL_INFERENCE
```

rather than:

```text
ARBITRARY_CODE
```

This massively reduces the attack surface.

---

# 14. Workload Model

Create a workload entity.

```text
workloads

id
project_id
node_id
model_id
status
input_hash
created_at
started_at
completed_at
cpu_seconds
gpu_seconds
memory_mb_seconds
tokens_in
tokens_out
error_code
```

Statuses:

```text
QUEUED
SCHEDULING
ASSIGNED
STARTING
RUNNING
COMPLETED
FAILED
CANCELLED
TIMEOUT
```

---

# 15. Workload Lifecycle

```text
              +---------+
              | QUEUED  |
              +----+----+
                   |
                   v
             SCHEDULING
                   |
                   v
               ASSIGNED
                   |
                   v
               STARTING
                   |
                   v
                RUNNING
               /       \
              /         \
             v           v
        COMPLETED      FAILED
```

Timeout:

```text
RUNNING
   |
   v
TIMEOUT
   |
   v
CLEANUP
```

---

# 16. Scheduler

This is the heart of AgentMesh.

Given:

```text
Workload requirements
```

find:

```text
Eligible nodes
```

Then rank them.

Initial scoring could be:

```text
score =
    capability_score
  + health_score
  + latency_score
  + reliability_score
  + price_score
```

Example:

```text
Node A
GPU: RTX 4090
Latency: 90ms
Reliability: 98%
Price: $0.30

Node B
GPU: A100
Latency: 140ms
Reliability: 99%
Price: $0.60

Node C
GPU: RTX 3080
Latency: 80ms
Reliability: 70%
Price: $0.15
```

For a demanding workload:

```text
Node B > Node A > Node C
```

For a cheap workload:

```text
Node A > Node C > Node B
```

Do not make the first scheduler complicated.

Start with hard requirements + weighted ranking.

---

# 17. Scheduling Constraints

A workload can specify:

```text
min_vram
gpu_required
model
max_latency
region
max_price
timeout
```

Example:

```json
{
  "model": "qwen2.5-7b",
  "requirements": {
    "gpu_required": true,
    "min_vram_gb": 16,
    "max_latency_ms": 500,
    "max_price_per_1k_tokens": 0.01
  }
}
```

Scheduler:

```text
1. filter
2. rank
3. reserve
4. dispatch
```

---

# 18. Prevent Double Scheduling

You need resource reservation.

Without it:

```text
Job A → Node 1
Job B → Node 1
Job C → Node 1
Job D → Node 1
```

all get scheduled before the node updates its status.

Instead:

```text
Node capacity
      |
      v
Reservation
      |
      v
Workload assigned
      |
      v
Resource locked
```

Use Redis for short-lived scheduling locks.

---

# 19. Model Registry

Do not allow nodes to arbitrarily advertise any model.

Create:

```text
models

id
name
version
runtime
container_image
checksum
requirements
status
created_at
```

Example:

```text
qwen2.5-7b
runtime: vllm
vram_required: 16GB
```

Models should be identified by immutable versions/digests.

Prefer:

```text
model:v1@sha256:...
```

over:

```text
latest
```

This protects against supply-chain confusion.

---

# 20. Model Supply Chain

This is another major security area.

A malicious provider should not be able to replace:

```text
official-model
```

with:

```text
malicious-model
```

Use:

- approved model registry
- immutable image digests
- SHA-256 checksums
- signed artifacts later
- restricted registry access

For the MVP:

```text
AgentMesh registry
        |
        v
Approved model
        |
        v
Immutable image
        |
        v
Node
```

---

# 21. Workload Isolation

For MVP, use containers.

Every workload gets:

```text
Container
    |
    +-- CPU limit
    +-- memory limit
    +-- GPU limit
    +-- timeout
    +-- temporary filesystem
    +-- restricted network
```

Never run workloads as root.

Never mount:

```text
/
/home
~/.ssh
/var/run/docker.sock
```

into customer workloads.

The Docker socket in particular would be catastrophic if exposed to an untrusted workload.

---

# 22. Container Security

Use:

- non-root user
- read-only root filesystem where possible
- dropped Linux capabilities
- seccomp
- AppArmor/SELinux where available
- CPU limits
- memory limits
- process limits
- execution timeout
- temporary filesystem
- no privileged mode
- no host networking
- no host PID namespace
- no host IPC
- no arbitrary device access

If you later use Kubernetes, target the **Restricted Pod Security Standard** for workload namespaces. Kubernetes' Restricted profile requires controls including non-root execution, disallowing privilege escalation, seccomp restrictions and dropping capabilities.

---

# 23. Network Security

Default policy:

```text
Workload
   |
   +----> AgentMesh control endpoint
   |
   +----> Approved model endpoint/registry if necessary
   |
   X----> arbitrary internet
```

Do not give workloads unrestricted outbound internet access.

Otherwise an attacker could use your network for:

- scanning
- spam
- attacks
- botnets
- data exfiltration
- command-and-control

For inference workloads, internet access should normally be **disabled**.

---

# 24. Secrets

Never inject your internal secrets into workloads.

A workload should never have access to:

```text
DATABASE_URL
PAYSTACK_SECRET_KEY
JWT_SECRET
NODE_PRIVATE_KEY
REDIS_PASSWORD
```

The node runtime and workload runtime must be separate security domains.

Kubernetes' security guidance similarly emphasizes secrets protection, workload isolation and network policies as separate security controls.

---

# 25. Data Security

There are two different data owners:

```text
Developer data
        |
        v
AgentMesh
        |
        v
Provider node
```

This is a trust boundary.

At minimum:

### In transit

Use TLS everywhere.

```text
Client → AgentMesh
AgentMesh → Node
Node → AgentMesh
```

### At rest

Encrypt sensitive platform data.

Do not unnecessarily persist inference inputs.

Prefer:

```text
request
   |
execute
   |
return result
   |
delete temporary input
```

rather than:

```text
request
   |
save forever
```

---

# 26. Sensitive Workloads

The MVP should explicitly tell developers:

> AgentMesh MVP uses third-party compute providers. Do not submit highly sensitive or regulated data unless the workload's security requirements are supported.

Later you can introduce:

```text
Trusted Node
Confidential Node
TEE Node
Enterprise Node
```

But don't pretend your MVP has confidential computing when it doesn't.

---

# 27. Node Reputation

A node should accumulate a reputation score.

Example:

```text
Node reputation

successful_jobs
failed_jobs
timeouts
uptime
latency
reported_capacity
job_completion_rate
```

Start simple:

```text
reputation =
    40% completion
    25% uptime
    20% latency
    15% consistency
```

Do not let reputation alone determine trust.

A node with 99% uptime is still an untrusted machine.

Reputation helps scheduling; it does not replace security isolation.

---

# 28. Provider Verification

MVP provider onboarding:

```text
Create provider account
       |
       v
Install node agent
       |
       v
Authenticate node
       |
       v
Hardware discovery
       |
       v
Health verification
       |
       v
Node becomes pending
       |
       v
Approved
```

For the first closed beta, **manually approve nodes**.

Do not immediately allow:

```text
random person on the internet
        ↓
install agent
        ↓
instantly serve customer workloads
```

That's asking for trouble.

---

# 29. Payment Architecture

Keep payment separate from workload execution.

```text
Developer
    |
    v
Payment Provider
    |
    v
AgentMesh Account Balance
    |
    v
Usage Ledger
    |
    v
Provider Earnings
```

Use Paystack or another supported payment processor for fiat payments.

Do not make the payment processor part of the scheduler.

Scheduler says:

```text
"This workload costs X."
```

Billing says:

```text
"Charge X."
```

Payment provider says:

```text
"Payment succeeded."
```

This separation matters.

---

# 30. Internal Ledger

Create:

```text
ledger_entries

id
account_id
type
amount
currency
reference
workload_id
created_at
```

Types:

```text
DEPOSIT
USAGE_CHARGE
REFUND
PROVIDER_EARNING
PLATFORM_FEE
PAYOUT
```

Never calculate balances purely from frontend state.

The backend owns the ledger.

---

# 31. Usage Metering

Track:

```text
input tokens
output tokens
GPU seconds
CPU seconds
execution duration
memory usage
```

For the MVP, choose **one primary pricing unit**.

I would use:

```text
per 1,000 tokens
```

for inference workloads where token accounting is reliable.

Then internally track hardware usage as well.

---

# 32. Billing Flow

```text
Workload starts
      |
      v
usage recorded
      |
      v
workload completes
      |
      v
calculate cost
      |
      v
ledger transaction
      |
      +----> platform revenue
      |
      +----> provider earning
```

Do not charge the frontend based on what it says the workload consumed.

The control plane calculates usage.

---

# 33. Failure Handling

Distributed systems fail constantly.

Assume:

```text
Node disappears.
GPU crashes.
Internet disconnects.
Container crashes.
Model fails.
Provider shuts down machine.
```

Your scheduler must handle this.

Example:

```text
Job
 |
 v
Node A
 |
 X
 |
 v
Node A timeout
 |
 v
Release reservation
 |
 v
Retry
 |
 v
Node B
 |
 v
Complete
```

Have:

```text
max_retries = 2
```

for MVP.

But be careful with non-idempotent workloads later.

---

# 34. Workload Timeout

Every workload must have a maximum execution time.

Example:

```text
timeout = 120 seconds
```

When exceeded:

```text
RUNNING
   |
   v
TIMEOUT
   |
   v
kill workload
   |
   v
release resources
   |
   v
retry or fail
```

A provider must never be allowed to run a workload forever.

---

# 35. Cancellation

Developer:

```text
POST /workloads/{id}/cancel
```

AgentMesh:

```text
QUEUED
    |
    v
CANCELLED
```

If running:

```text
RUNNING
    |
    v
termination request
    |
    v
container killed
    |
    v
resources released
```

---

# 36. Result Integrity

For every execution generate:

```text
execution_id
workload_id
node_id
started_at
completed_at
runtime_version
model_digest
result_hash
```

This creates an execution record.

Example:

```text
execution:
exec_123

node:
node_456

model:
qwen2.5-7b@sha256:abc...

result:
sha256:def...
```

This doesn't prove that the provider honestly executed the workload.

It does provide an auditable execution trail.

---

# 37. Do Not Claim “Verified Compute” Yet

This distinction is extremely important.

In MVP:

```text
Node says:
"I executed it."
```

You record that.

You do NOT claim:

```text
"Cryptographically proven that this exact GPU executed the workload."
```

True verification can eventually involve:

- remote attestation
- trusted execution environments
- redundant execution
- result comparison
- verifiable computation

But those are later research/engineering problems.

---

# 38. API Design

Version the API immediately.

```text
/api/v1
```

Core endpoints:

```text
POST   /v1/auth/register
POST   /v1/auth/login

POST   /v1/projects
GET    /v1/projects

POST   /v1/api-keys
DELETE /v1/api-keys/{id}

POST   /v1/workloads
GET    /v1/workloads
GET    /v1/workloads/{id}
POST   /v1/workloads/{id}/cancel

GET    /v1/models
GET    /v1/usage

GET    /v1/account/balance
GET    /v1/account/transactions
```

Node endpoints:

```text
POST /v1/nodes/register
POST /v1/nodes/heartbeat
GET  /v1/nodes/{id}
POST /v1/nodes/{id}/status
```

Internal endpoints should be separated from public APIs.

---

# 39. Authorization

Use RBAC.

Minimum roles:

```text
USER
PROVIDER
ADMIN
```

Potentially:

```text
USER
PROVIDER
SUPPORT
ADMIN
```

A developer must not be able to call:

```text
POST /admin/nodes/suspend
```

A node must not be able to call:

```text
GET /users
```

Every service operation needs authorization.

---

# 40. Rate Limiting

At minimum:

```text
login:
10 requests/minute/IP

API:
100 requests/minute/project

workload creation:
specific quota

node heartbeat:
controlled fixed rate
```

Do not allow an API key to create unlimited workloads.

Create quotas:

```text
requests_per_minute
tokens_per_day
concurrent_jobs
monthly_spend_limit
```

---

# 41. Abuse Prevention

The platform will eventually attract people trying to abuse cheap compute.

You need controls against:

```text
cryptomining
spam generation
network attacks
port scanning
malware execution
credential attacks
proxy abuse
illegal workloads
resource exhaustion
```

The easiest MVP defense:

**Only support predefined inference workloads.**

Do not expose arbitrary shell/code execution.

---

# 42. Admin Dashboard

The admin dashboard should show:

```text
Nodes
-----
Online: 12
Busy: 7
Offline: 3

Workloads
---------
Running: 34
Queued: 8
Failed: 2

Infrastructure
--------------
GPU capacity
CPU capacity
RAM
Network latency

Security
--------
Suspicious nodes
Failed authentication
Rate-limit violations
Workload failures

Finance
-------
Platform revenue
Provider earnings
Pending payouts
```

---

# 43. Developer Dashboard

Keep it simple.

```text
AgentMesh

Balance
$25.40

Usage
1.8M tokens

Active workloads
3

Recent workloads
----------------
Qwen inference     completed
Llama inference    running
Vision inference   completed
```

And:

```text
API Keys
Models
Usage
Billing
Projects
```

Do not build a huge dashboard.

---

# 44. Provider Dashboard

Provider should see:

```text
Node Status
ONLINE

GPU
RTX 4090

VRAM
24 GB

Current Utilization
67%

Jobs
124

Successful
119

Failed
5

Estimated Earnings
₦XX,XXX
```

Plus:

```text
Pause node
Restart agent
View logs
View workloads
Payout history
```

---

# 45. Logging

Every important operation should generate structured logs.

Example:

```json
{
  "timestamp": "...",
  "request_id": "req_123",
  "workload_id": "job_456",
  "node_id": "node_789",
  "event": "workload_completed",
  "duration_ms": 842,
  "status": "success"
}
```

Do not log:

```text
passwords
API keys
tokens
payment secrets
raw sensitive prompts
```

---

# 46. Audit Logs

Separate application logs from security audit logs.

Audit:

```text
user_created
api_key_created
api_key_revoked
node_registered
node_suspended
workload_created
workload_cancelled
admin_login
admin_action
payment_created
payout_created
```

Audit logs should be append-only from the application perspective.

---

# 47. Monitoring

Track:

```text
API latency
API errors
queue depth
scheduler latency
workload success rate
workload failure rate
node availability
node heartbeat failures
GPU utilization
billing errors
authentication failures
```

Metrics:

```text
request_latency
workloads_total
workloads_failed_total
nodes_online
nodes_offline
queue_depth
tokens_processed
gpu_seconds
```

---

# 48. Observability Stack

For MVP:

```text
Application
    |
    +--> structured logs
    |
    +--> metrics
    |
    +--> traces
```

You can use:

```text
Prometheus
Grafana
OpenTelemetry
```

Don't overengineer it.

---

# 49. Database Model

Core tables:

```text
users
projects
api_keys

providers
nodes
node_heartbeats

models

workloads
executions

usage_records

accounts
ledger_entries
payouts

audit_logs
```

Important relationships:

```text
User
 |
 +-- Projects
       |
       +-- API Keys
       |
       +-- Workloads
              |
              +-- Execution
                     |
                     +-- Node
```

---

# 50. Security Architecture

Think in security boundaries.

```text
                 INTERNET
                    |
                    v
             +-------------+
             | API Gateway |
             +-------------+
                    |
             AUTHENTICATION
                    |
                    v
             +-------------+
             | Control     |
             | Plane       |
             +-------------+
                    |
             scheduling only
                    |
                    v
             +-------------+
             | Dispatcher  |
             +-------------+
                    |
              authenticated
               node channel
                    |
                    v
             +-------------+
             | Node Agent  |
             +-------------+
                    |
              isolated runtime
                    |
                    v
             +-------------+
             | Workload    |
             | Container   |
             +-------------+
```

The control plane should never blindly trust the workload container.

The node agent should never blindly trust the workload.

The workload should have almost no privileges.

---

# 51. Threat Model

Before coding the distributed part, document these attackers.

## Attacker 1 — Malicious developer

Goal:

```text
abuse compute
```

Controls:

- authentication
- quotas
- rate limits
- predefined workload types
- spending limits
- abuse monitoring

## Attacker 2 — Malicious node provider

Goal:

```text
steal data
```

Controls:

- minimize data retention
- encryption
- workload isolation
- node reputation
- trusted-node tiers later
- sensitive workload restrictions

## Attacker 3 — Compromised node

Goal:

```text
attack AgentMesh
```

Controls:

- zero-trust authentication
- limited node permissions
- credential rotation
- node revocation
- strict API authorization

## Attacker 4 — Malicious workload

Goal:

```text
escape container
```

Controls:

- non-root
- seccomp
- AppArmor/SELinux
- no privileged containers
- no host mounts
- no Docker socket
- resource limits
- restricted networking

## Attacker 5 — API attacker

Goal:

```text
take over account
```

Controls:

- secure authentication
- rate limiting
- API key rotation
- audit logging
- session management
- MFA later

---

# 52. Zero-Trust Principle

The architecture should assume:

```text
Internet = untrusted
Developer = untrusted
Node = untrusted
Workload = untrusted
Provider = partially trusted
```

Only grant the minimum permission required.

This follows the core zero-trust principle that access should not be implicitly trusted based merely on network location or ownership.

---

# 53. CI/CD Security

Every pull request should run:

```text
lint
unit tests
integration tests
security scanning
dependency scanning
container scanning
```

Build pipeline:

```text
GitHub
   |
   v
Tests
   |
   v
Security Scan
   |
   v
Build
   |
   v
Container Scan
   |
   v
Deploy
```

Never deploy directly from someone's laptop.

---

# 54. Dependency Security

Use:

```text
lockfiles
Dependabot/Renovate
SBOM generation
dependency vulnerability scanning
```

Pin important infrastructure images.

Avoid:

```text
FROM something:latest
```

Prefer immutable versions/digests for production deployments.

---

# 55. Container Image Security

Your node agent should only run approved images.

Example:

```text
agentmesh/inference-runtime@sha256:...
```

Not:

```text
agentmesh/inference-runtime:latest
```

Scan images before publishing.

---

# 56. Secret Management

Development:

```text
.env
```

Production:

Use a proper secret manager.

Examples:

```text
Vault
AWS Secrets Manager
GCP Secret Manager
Doppler
```

Never commit:

```text
.env
API keys
private keys
payment secrets
database passwords
```

to Git.

---

# 57. Node Credential Lifecycle

A node credential must support:

```text
ISSUED
ACTIVE
ROTATED
REVOKED
EXPIRED
```

If a node is compromised:

```text
ADMIN
  |
  v
REVOKE NODE
  |
  v
Node loses access
```

Do not require redeploying the entire platform.

---

# 58. Model Security

The model itself is part of your supply chain.

Track:

```text
model name
version
source
checksum
runtime
license
requirements
```

Only approved models are executable in the MVP.

---

# 59. Security Testing

Before opening AgentMesh to outside providers, test:

### API

- authentication bypass
- authorization bypass
- IDOR
- rate-limit bypass
- malformed input
- oversized input

### Node

- credential theft
- node impersonation
- replay attacks
- unauthorized workload retrieval

### Runtime

- container escape attempts
- filesystem access
- network access
- privilege escalation
- resource exhaustion

### Billing

- duplicate charges
- negative balances
- replayed payments
- double payouts
- race conditions

---

# 60. Concurrency Testing

You absolutely need tests for:

```text
two schedulers
same node
same workload
same payment
same reservation
```

Distributed systems fail in race conditions.

For example:

```text
Scheduler A → Node 1 available
Scheduler B → Node 1 available

A → reserve Node 1
B → reserve Node 1
```

Only one should succeed.

Use database transactions and/or distributed locking where appropriate.

---

# 61. MVP Deployment Architecture

Initially:

```text
                  Internet
                     |
                     v
                Cloud/VPS
                     |
             +-------+-------+
             |               |
             v               v
          Dashboard        API
                             |
                  +----------+----------+
                  |                     |
                  v                     v
              PostgreSQL             Redis
                                        |
                                        v
                                      Queue
                                        |
                                        v
                                    Scheduler
                                        |
                         secure outbound connection
                                        |
               +------------------------+------------------+
               |                        |                  |
               v                        v                  v
            Node A                   Node B             Node C
            GPU                     GPU/CPU              GPU
```

Start with perhaps:

```text
1 control server
2–5 trusted nodes
1–2 models
```

That is enough to prove the architecture.

---

# 62. Do NOT Start With Hundreds of Nodes

Your first milestone should be:

```text
3 nodes
1 developer
1 workload
1 successful execution
```

Then:

```text
3 nodes
10 developers
100 workloads
```

Then:

```text
10 nodes
```

Then scale.

You need to prove the system before worrying about “decentralization at internet scale.”

---

# 63. MVP Development Phases

## Phase 1 — Control Plane

Build:

```text
API
Database
Authentication
Projects
API keys
```

Success:

```text
developer can authenticate
developer gets API key
```

---

## Phase 2 — Node Agent

Build:

```text
node registration
hardware discovery
heartbeat
node status
```

Success:

```text
AgentMesh dashboard shows:

Node A
RTX 4090
ONLINE
```

---

## Phase 3 — Model Runtime

Deploy:

```text
one model
one runtime
```

Success:

```text
Node A
   |
   v
Inference runtime
   |
   v
returns result
```

---

## Phase 4 — Workload Dispatcher

Build:

```text
queue
scheduler
reservation
dispatcher
execution tracking
```

Success:

```text
API request
    ↓
Scheduler
    ↓
Node B
    ↓
Inference
    ↓
Result
```

---

## Phase 5 — Security Hardening

Before onboarding external nodes:

```text
container isolation
network restrictions
resource limits
credential rotation
audit logs
rate limiting
security tests
```

This phase is **mandatory**.

---

## Phase 6 — Metering

Track:

```text
execution time
tokens
GPU usage
```

Calculate:

```text
workload cost
```

---

## Phase 7 — Billing

Implement:

```text
account
deposit
usage charge
provider earnings
platform fee
```

Integrate Paystack after the internal ledger works.

---

## Phase 8 — Dashboard

Build:

```text
developer dashboard
provider dashboard
admin dashboard
```

---

# 64. Definition of Done

The MVP is not finished because:

```text
"the dashboard looks good."
```

It is finished when this complete flow works:

```text
Developer
   |
   | API key
   v
AgentMesh API
   |
   | workload
   v
Scheduler
   |
   | selects node
   v
Node Agent
   |
   | starts isolated runtime
   v
AI Model
   |
   | result
   v
Node Agent
   |
   v
AgentMesh
   |
   +--> usage meter
   |
   +--> billing ledger
   |
   v
Developer
```

And the system survives:

```text
node failure
API failure
invalid request
expired credential
workload timeout
duplicate request
duplicate payment event
malicious workload
resource exhaustion
```

---

# 65. MVP Acceptance Tests

### Test 1

Register node.

Expected:

```text
Node appears as PENDING.
```

### Test 2

Approve node.

Expected:

```text
Node becomes ONLINE.
```

### Test 3

Submit inference.

Expected:

```text
Workload → QUEUED.
```

### Test 4

Scheduler selects node.

Expected:

```text
Workload → ASSIGNED.
```

### Test 5

Node executes.

Expected:

```text
Workload → RUNNING.
```

### Test 6

Inference succeeds.

Expected:

```text
Workload → COMPLETED.
```

### Test 7

Node disappears.

Expected:

```text
Workload → retry.
```

### Test 8

Workload exceeds timeout.

Expected:

```text
Container killed.
Resources released.
```

### Test 9

Developer exceeds quota.

Expected:

```text
Request rejected.
```

### Test 10

Provider credential revoked.

Expected:

```text
Node can no longer receive workloads.
```

### Test 11

Malicious container attempts privilege escalation.

Expected:

```text
Execution blocked.
```

### Test 12

Duplicate billing event arrives.

Expected:

```text
Only one ledger transaction.
```

---

# 66. What Makes AgentMesh Different

Do not sell this:

> "We have distributed GPUs."

That's not enough.

The product should eventually be:

> **AgentMesh gives AI applications an intelligent execution layer that automatically finds and uses suitable compute wherever it exists.**

The architecture becomes:

```text
                APPLICATION
                     |
                     v
                AGENTMESH
                     |
          +----------+----------+
          |          |          |
          v          v          v
       MODEL      COMPUTE     POLICY
      ROUTING     ROUTING     ENGINE
          |          |          |
          +----------+----------+
                     |
                     v
              DISTRIBUTED NODES
```

That is the bigger vision.

---

# 67. Long-Term Architecture

Once the MVP works:

```text
                         AGENTMESH
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
     Agent Runtime       Model Registry     Scheduler
          |                  |                  |
          +------------------+------------------+
                             |
                       Node Network
                             |
          +-----------+------+-------+-----------+
          |           |              |           |
          v           v              v           v
       GPU Node    GPU Node       CPU Node    Edge Node
```

Then you can introduce:

```text
trusted execution
remote attestation
enterprise nodes
private clusters
multi-region routing
model caching
distributed inference
agent-to-agent execution
automatic failover
advanced reputation
```

But **only after the basic execution marketplace works**.

---

# 68. Engineering Principle

The most important principle for the entire project is:

> **Treat every workload and every external node as potentially hostile.**

Your architecture should assume:

```text
Customer can be malicious.
Provider can be malicious.
Node can be compromised.
Network can fail.
Model can be compromised.
Payment can be replayed.
Requests can be duplicated.
```

That mindset is much more appropriate for AgentMesh than simply building another AI dashboard.

---

# 69. The First Actual Build Target

Do not start by building the landing page.

Do not start with payments.

Do not start with the marketplace.

Build this:

```text
                    AGENTMESH MVP

Developer
    |
    | POST /v1/workloads
    v
Control Plane
    |
    v
Scheduler
    |
    v
Node Registry
    |
    v
Node Agent
    |
    v
Docker
    |
    v
vLLM / Model
    |
    v
Result
    |
    v
Control Plane
    |
    +----> Usage
    |
    +----> Audit
    |
    +----> Billing
    |
    v
Developer
```

If you can make **that flow reliable and secure with three real machines**, you have something worth showing people.

If you cannot make that flow work, adding blockchain, fancy agents, beautiful dashboards or hundreds of nodes won't save the product.

---

# 70. Final MVP Checklist

### Core

- [ ] Developer authentication
- [ ] Projects
- [ ] API keys
- [ ] Node registration
- [ ] Node authentication
- [ ] Node heartbeat
- [ ] Hardware discovery
- [ ] Model registry
- [ ] Workload API
- [ ] Scheduler
- [ ] Resource reservation
- [ ] Workload dispatcher
- [ ] Container runtime
- [ ] Inference runtime
- [ ] Result handling
- [ ] Retry system
- [ ] Timeout system

### Security

- [ ] TLS
- [ ] hashed API keys
- [ ] credential rotation
- [ ] node revocation
- [ ] RBAC
- [ ] rate limiting
- [ ] workload quotas
- [ ] non-root containers
- [ ] seccomp
- [ ] capability dropping
- [ ] no privileged containers
- [ ] no host mounts
- [ ] no Docker socket
- [ ] resource limits
- [ ] network restrictions
- [ ] secret isolation
- [ ] model integrity checks
- [ ] audit logs
- [ ] security monitoring

### Reliability

- [ ] heartbeats
- [ ] health checks
- [ ] reservations
- [ ] retry
- [ ] timeout
- [ ] cancellation
- [ ] node failure handling
- [ ] idempotency
- [ ] database transactions
- [ ] queue persistence

### Billing

- [ ] account balance
- [ ] usage meter
- [ ] immutable ledger
- [ ] platform fee
- [ ] provider earnings
- [ ] payment integration
- [ ] payout tracking
- [ ] duplicate-payment protection

### Developer Experience

- [ ] REST API
- [ ] API documentation
- [ ] SDK
- [ ] workload status
- [ ] usage dashboard
- [ ] API key management

### Operations

- [ ] structured logging
- [ ] metrics
- [ ] health endpoints
- [ ] alerts
- [ ] CI/CD
- [ ] dependency scanning
- [ ] container scanning
- [ ] integration tests
- [ ] security tests
- [ ] load tests

---

## The actual MVP boundary

**Build:**

```text
Developer
    ↓
API
    ↓
Scheduler
    ↓
Trusted distributed nodes
    ↓
Isolated inference
    ↓
Result
    ↓
Usage
    ↓
Billing
```

**Don't build yet:**

```text
Blockchain
Token
DAO
Arbitrary code execution
Permissionless global nodes
TEE infrastructure
Cryptographic proof of compute
Complex agent-to-agent networks
Multi-cloud Kubernetes federation
```

That gives you a **real engineering product**, rather than a hackathon architecture diagram.

And importantly, the security model is not an afterthought. Because AgentMesh crosses the trust boundary between customers and independently operated machines, **isolation, identity, authorization, resource controls, network restrictions and auditability are part of the core product**. NIST's AI risk-management guidance is also a useful higher-level framework for treating generative-AI risks systematically, while Kubernetes provides concrete workload-hardening controls if/when you move the execution layer onto Kubernetes.