# AgentMesh

AgentMesh lets developers deploy open-weight AI models on computers contributed by independent providers and
call them through an OpenAI-compatible API. Workloads run inside resource limits on the provider's machine; the
provider can see the data a workload handles (see the trust model in [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)).
Billing is prepaid, with Paystack top-ups and provider payouts. These run in Paystack test mode and have not
yet been exercised against Paystack's live API.

## Architecture

![AgentMesh System Architecture](./systemarchitecture.png)

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 16
- Redis 7

## Quick Start (Development)

1. Clone the repository
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Start infrastructure services:
   ```bash
   docker-compose up -d postgres redis
   ```
4. Setup Backend (Control Plane):
   ```bash
   cd server
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload
   ```
5. Setup Frontend (Dashboard):
   ```bash
   cd client
   npm install
   npm run dev
   ```
6. Run a worker (in a new terminal). See [docs/WORKER.md](docs/WORKER.md) for both node modes:
   ```bash
   cd server
   python -m node_agent enroll --token <token from POST /api/v1/nodes/enrollment-tokens>
   python -m node_agent run
   ```

For providers, `server/packaging/install.sh` installs the worker as a per-user background service (no root);
see [docs/WORKER.md](docs/WORKER.md).

To call a deployed model, see [docs/INFERENCE_API.md](docs/INFERENCE_API.md). For the customer, provider and
operator workflows (dashboard and API), see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

Running a network in production (configuration, Paystack, monitoring, backups, recovery):
[docs/OPERATIONS.md](docs/OPERATIONS.md). Security review and residual risks:
[docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md).

Operators cannot self-register. Create the first operator account on the server:

```bash
cd server
python scripts/create_operator.py ops@example.com
```

### End-to-end check

```bash
cd server
DATABASE_URL=sqlite+aiosqlite:///./dev.db python scripts/init_dev_db.py
DATABASE_URL=sqlite+aiosqlite:///./dev.db uvicorn app.main:app --port 8000 &
python scripts/e2e_ollama.py --api http://127.0.0.1:8000 --model smollm2:135m
```

Failover across two local workers (start the API with `WORKER_HEARTBEAT_INTERVAL_SECONDS=3
HEARTBEAT_TIMEOUT_SECONDS=12 UNHEALTHY_GRACE_SECONDS=15` so it finishes quickly):

```bash
python scripts/e2e_failover.py --api http://127.0.0.1:8000 --model smollm2:135m
```

## Running tests

```bash
cd server
pytest                      # in-memory SQLite by default
TEST_DATABASE_URL=postgresql+asyncpg://agentmesh:agentmesh@localhost:5432/agentmesh_test pytest

cd client
npx tsc --noEmit && npx jest && npm run build
```

The browser end-to-end test (real control plane, real worker, real model, all three dashboards) is described in
[client/e2e/README.md](client/e2e/README.md).

## Project status

What works, what is missing, and the phased plan are tracked in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).


## Makefile Commands

A comprehensive `Makefile` is provided. Run `make help` or refer to the Makefile itself for all available commands.

## Docker Deployment

To deploy using Docker:
```bash
make docker-build
docker-compose up -d
```

## Contributing

See `CONTRIBUTING.md` for guidelines.

## License

MIT License.


