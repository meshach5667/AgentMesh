# End-to-end product test

`product.spec.ts` drives the dashboards in a real browser against a real control plane, a real installable-agent
worker and a real model (SmolLM2 135M through an isolated Ollama instance started by the worker; your own Ollama
service is not used). It downloads the model (about 270 MB) into a temporary worker data directory.

```bash
# 1. Control plane on a throwaway MongoDB database (a replica set, e.g. `mongod --replSet rs0` + rs.initiate())
cd server
export MONGODB_URL='mongodb://127.0.0.1:27017/?replicaSet=rs0' MONGODB_DB=agentmesh_e2e
AGENTMESH_OPERATOR_PASSWORD=e2e-operator-password venv/bin/python scripts/create_operator.py ops@example.com
venv/bin/uvicorn app.main:app --port 8000

# 2. Dashboard (production build)
cd client && npm run build && npm run start

# 3. The test (uses installed Google Chrome; omit PLAYWRIGHT_CHANNEL to use Playwright's Chromium)
cd client
E2E_OPERATOR_EMAIL=ops@example.com E2E_OPERATOR_PASSWORD=e2e-operator-password \
  PLAYWRIGHT_CHANNEL=chrome npx playwright test
```

Prices and payment: the provider publishes a profile, a payment arrangement and a price for its machine;
the customer finds it under Compute providers, deploys with no balance (customers pay providers directly),
and both sides then see the same payment reference next to the cost estimate. For the estimate step to
finish quickly, start the API with `COST_ESTIMATE_INTERVAL_SECONDS=60 MONITOR_INTERVAL_SECONDS=5`.

Optional: `E2E_API` (default `http://localhost:8000`), `E2E_PYTHON` (default `../server/venv/bin/python`),
`E2E_MODEL` (catalog name, default `SmolLM2 135M`).
