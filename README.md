# AgentMesh

AgentMesh is a decentralized platform for deploying and running AI models securely and efficiently.

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

To call a deployed model, see [docs/INFERENCE_API.md](docs/INFERENCE_API.md).

### End-to-end check

```bash
cd server
DATABASE_URL=sqlite+aiosqlite:///./dev.db python scripts/init_dev_db.py
DATABASE_URL=sqlite+aiosqlite:///./dev.db uvicorn app.main:app --port 8000 &
python scripts/e2e_ollama.py --api http://127.0.0.1:8000 --model smollm2:135m
```

## Running tests

```bash
cd server
pytest                      # in-memory SQLite by default
TEST_DATABASE_URL=postgresql+asyncpg://agentmesh:agentmesh@localhost:5432/agentmesh_test pytest
```

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


# TODO

- Implement the node installation