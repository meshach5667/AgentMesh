# Security Policy

AgentMesh is an open-source platform that runs open-weight AI models on machines contributed by independent providers. This file explains how to report a vulnerability and what to expect after you do.

## Supported versions

| Component | Supported |
|---|---|
| Control plane and dashboard (`server/app`, `client/`) | The `main` branch and the version deployed from it |
| Worker (`server/node_agent`) | The latest published worker release (currently `0.3.0`) and `main` |
| Older worker releases | Not supported. Upgrade first; workers update themselves with signed releases. |

## Reporting a vulnerability

**Please do not open a public issue, pull request or discussion about a security problem.**

Report it privately through GitHub's private vulnerability reporting:
<https://github.com/meshach5667/AgentMesh/security/advisories/new>

Include:
- what is affected (component, endpoint or file);
- steps to reproduce, or a proof of concept;
- the impact you believe it has;
- any logs or requests, with real credentials and personal data removed.

If you cannot use GitHub, email meshachzakumi@gmail.com with "AgentMesh security" in the subject.

## What to expect

| Step | Target time |
|---|---|
| Acknowledgement of your report | 3 business days |
| First assessment (accepted, needs information, or not a vulnerability) | 10 business days |
| Fix or mitigation for critical and high severity issues | as soon as practical, normally within 30 days |
| Public advisory | after a fix is released, credited to you unless you prefer otherwise |

We will keep you updated while we work on it, and will tell you if we disagree with the severity.

## Safe harbor

We will not pursue or support legal action against anyone who, in good faith:
- reports a vulnerability privately as described above;
- avoids privacy violations, data destruction and service disruption;
- accesses only the data needed to show the problem, and stops and reports as soon as they reach other people's data;
- does not use social engineering, physical attacks, or attacks on our hosting, payment or other service providers;
- tests only against their own accounts, their own nodes, or a local deployment of AgentMesh;
- gives us reasonable time to fix the issue before disclosing it.

If in doubt about whether something is in scope, ask first through the private reporting channel.

## Scope notes

- **Known, documented limitation:** a provider with root access on its own machine can read the prompts and outputs that machine processes. Reports that restate this are not vulnerabilities. Ways to bypass the controls that limit it (node isolation, signed commands, revocation) are in scope.
- Findings in third-party services (Paystack, MongoDB Atlas, Render, Vercel, GitHub) should go to those vendors.

## How AgentMesh handles security

- Threat model, trust boundaries and accepted risks: [`docs/security/THREAT_MODEL.md`](docs/security/THREAT_MODEL.md)
- Who may do what: [`docs/security/PERMISSIONS.md`](docs/security/PERMISSIONS.md)
- Data classes, retention and deletion: [`docs/security/DATA_HANDLING.md`](docs/security/DATA_HANDLING.md)
- Incident response, key rotation and release rollback: [`docs/security/INCIDENT_RESPONSE.md`](docs/security/INCIDENT_RESPONSE.md)
- Latest audit and implementation status: [`docs/security/GAP_REPORT.md`](docs/security/GAP_REPORT.md), [`docs/security/IMPLEMENTATION_REPORT.md`](docs/security/IMPLEMENTATION_REPORT.md)

AgentMesh has not had an independent security audit and makes no compliance or certification claims.

### Supply chain

- CI pins every third-party action to a full commit SHA and gives workflows a read-only token. Workflows triggered by pull requests from forks get no secrets.
- Images use digest-pinned base images and install from `server/requirements-lock.txt` and `server/requirements-worker-lock.txt`. After changing `requirements.txt` or `requirements-worker.txt`, regenerate the lock files from a tested environment and run `pytest tests/test_ci_policy.py`.
- Every pull request runs dependency, secret, static-analysis, container and configuration scans. Worker release assets carry Sigstore build-provenance attestations, and worker self-updates are signed with an offline key.
