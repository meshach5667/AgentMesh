# AgentMesh Security Policy & Architecture

## 1. Overview

AgentMesh connects compute providers (third-party GPU/CPU machine owners) with AI model consumers via an autonomous orchestration plane. Because workloads run on untrusted or third-party infrastructure and customers consume endpoints without direct physical control, security is a fundamental design requirement across both the control plane and compute plane.

This document outlines AgentMesh's security model, principles, implementation details, reporting procedures, and operational best practices.

---

## 2. Core Security Principles

1. **Principle of Least Privilege**:
   - AI Agents operate exclusively via bounded, auditable tools (`find_capable_nodes`, `deploy_model`, `stop_deployment`). Agents **never** have raw shell/SSH access to compute nodes or database instances.
   - Customers interact with deployed inference endpoints via managed proxies/gateways without host shell access.

2. **Defense in Depth**:
   - Authentication is required at every boundary (User $\leftrightarrow$ Control Plane, Node Agent $\leftrightarrow$ Control Plane, Customer $\leftrightarrow$ Inference Endpoint).
   - Network boundaries enforce strict CORS, payload validation, rate-limiting, and TLS encryption.

3. **Isolated Workload Sandboxing**:
   - Model runtimes (e.g. vLLM, Ollama) run inside sandboxed Docker containers with explicit resource constraints (CPU, RAM, GPU device requests).
   - The host Docker socket is never mounted into user model containers.

4. **Immutable Audit Trails**:
   - Financial ledger entries (wallets, usage records, charges, platform fees) and agent operations are recorded with idempotency keys and audit log entries.

---

## 3. Threat Model & Mitigations

| Threat | Target | Mitigation Strategy |
| :--- | :--- | :--- |
| **Rogue / Malicious Node** | Model Weights / Customer Requests | Approved containerized runtimes only; secure TLS tunnels; cryptographic node identity registration; future support for confidential computing (TEE) and verifiable compute. |
| **Untrusted Model / Prompt Injection** | Node Host Infrastructure | Workloads run inside unprivileged containers; host filesystem access is restricted; container escapes mitigated via non-root execution and resource limits. |
| **Identity / Node Spoofing** | Control Plane / Node Registry | Asymmetric RSA-2048 keypair generation on node initialization; cryptographic signatures on registration; hashed API key tokens stored in DB. |
| **Replay & MitM Attacks** | Heartbeats / Deployment Orders | HTTPS / TLS encryption for all control-plane APIs; short-lived JWT tokens (HS256/RS256); timestamped and nonce-verified heartbeats. |
| **Financial / Usage Tampering** | Ledger & Wallets | Atomic DB transactions for all ledger operations (`settle_usage`); deterministic fee splits (90% provider / 10% platform); immutable usage log entries. |
| **Agent Hallucination / Overreach** | Compute Infrastructure | Deterministic safety policies and hard filters; explicit tool definitions with JSON schema validation; human-in-the-loop overrides for administrative actions. |

---

## 4. Authentication & Identity

### 4.1 User Authentication (Providers, Customers, Operators)
- **Mechanism**: JSON Web Tokens (JWT) using `HS256` (configurable to `RS256`).
- **Passwords**: Hashed using `bcrypt` (Passlib context) with unique salts.
- **Role-Based Access Control (RBAC)**:
  - `provider`: Manage owned nodes, set pricing, view earnings, configure hardware.
  - `customer`: Browse marketplace/model catalog, deploy models, manage wallet, view usage.
  - `operator` / `admin`: Manage model registry approvals, view network-wide metrics, handle dispute settlements.

### 4.2 Node Agent Authentication
- **Initial Setup**: Each Node Agent automatically creates an RSA-2048 keypair on first run (`~/.agentmesh/node/node_key.pem`).
- **Registration**: The public key is submitted to the Control Plane alongside discovered hardware specs. The Control Plane issues a unique `node_id` and hashed API secret token.
- **Node-to-Cloud Calls**: All subsequent requests (Heartbeats, Metrics, Usage reports) require the Node Bearer API token.
- **Cloud-to-Node Orders**: Node agents validate incoming deployment requests against the control plane token before executing container operations.

---

## 5. Workload Isolation & Runtime Security

1. **Approved Runtimes Only**:
   - Only curated, vetted container images (`vllm/vllm-openai:latest`, `ollama/ollama:latest`) are executed by default.
   - Arbitrary user-supplied Dockerfiles or unvetted container images are prohibited in the MVP.

2. **Resource Boundaries**:
   - Memory limits (`--memory`), CPU quotas (`--cpus`), and explicit NVIDIA device allocations (`DeviceRequest(capabilities=[['gpu']])`) prevent rogue containers from starving node hosts.

3. **Network Isolation**:
   - Model containers bind to internal, ephemeral ports on local loops and expose only standard HTTP inference interfaces (`/v1/completions`, `/v1/chat/completions`).

4. **Secret Management**:
   - Host secrets and platform database credentials are never injected into model runtime containers.

---

## 6. Financial & Ledger Security

- **Atomic Transactions**: Balance deductions, provider payouts, and platform fee splits are executed within strict ACID transaction blocks in PostgreSQL with rollback on failure.
- **Idempotency**: All payment transactions include an idempotency reference (`reference` field) preventing double-spend or duplicate billing from retried network requests.
- **Fee Integrity**: Platform fee rate is locked and enforced centrally by the `payment_service` (default `10%`).

---

## 7. Security in CI/CD & Automated Verification

AgentMesh incorporates continuous automated security checks on every pull request and push to `main`:

- **Dependency Audits**: Automated checks via `pip-audit` for Python and `npm audit` for frontend dependencies.
- **Static Analysis & Type Safety**: `mypy` and `tsc --noEmit` enforce type correctness; `ruff` and `eslint` enforce strict linting rules.
- **Container Vulnerability Scanning**: Trivy scans Docker images for known CVEs.
- **Secret Scanning**: Gitleaks / TruffleHog inspects commits to prevent credential leakage.

---

## 8. Reporting a Vulnerability

We take the security of AgentMesh seriously. If you discover a vulnerability, please report it responsibly.

### How to Report:
- **Email**: Send vulnerability reports to `security@agentmesh.network` (or open a confidential security advisory on GitHub).
- **Include**:
  - Detailed description of the vulnerability.
  - Steps to reproduce (Proof of Concept scripts, API payloads).
  - Potential impact and affected components.
- **Response SLA**:
  - Initial Acknowledgement: Within 48 hours.
  - Triage & Assessment: Within 5 business days.

> **Please do not report security vulnerabilities through public GitHub issues.**

---

## 9. Security Best Practices for Operators & Providers

- Always keep the Node Agent and Docker engine updated to the latest supported versions.
- Ensure the `SECRET_KEY` and database passwords in `.env` are cryptographically random and never checked into version control.
- Restrict firewall access so that Node Agent API ports (default `8001`) and inference ports are accessible only to authorized proxies or VPN overlays.
- Rotate node API keys if a node host is decommissioned or compromised.
