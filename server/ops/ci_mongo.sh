#!/usr/bin/env bash
# Start a single-node MongoDB replica set for CI and wait until it accepts writes (ledger postings need transactions,
# so a replica set is required).
#
#   server/ops/ci_mongo.sh            # then use mongodb://localhost:27017/?replicaSet=rs0
#
# Runs mongod directly on the runner instead of in a container: MongoDB 8.0 server, shell and database tools are
# installed from MongoDB's official apt repository when no mongod 7+ is on PATH. On failure it prints mongod's log.
set -euo pipefail

PORT="${MONGO_PORT:-27017}"
WORK="${RUNNER_TEMP:-/tmp}/agentmesh-mongo"
DATA="$WORK/data"
LOG="$WORK/mongod.log"

have_mongod() {
  command -v mongod >/dev/null 2>&1 || return 1
  local major
  major=$(mongod --version | sed -n 's/^db version v\([0-9]*\).*/\1/p')
  [[ -n "$major" && "$major" -ge 7 ]]
}

if ! have_mongod || ! command -v mongosh >/dev/null 2>&1 || ! command -v mongodump >/dev/null 2>&1; then
  codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
  keyring=/usr/share/keyrings/mongodb-server-8.0.gpg
  curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | sudo gpg --batch --yes --dearmor -o "$keyring"
  echo "deb [ arch=amd64,arm64 signed-by=$keyring ] https://repo.mongodb.org/apt/ubuntu ${codename}/mongodb-org/8.0 multiverse" \
    | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq mongodb-org-server mongodb-mongosh mongodb-database-tools >/dev/null
fi
mongod --version | head -1

fail() {
  echo "::error::$1"
  echo "--- mongod log (last 50 lines) ---"
  tail -n 50 "$LOG" 2>/dev/null || true
  exit 1
}

mkdir -p "$DATA"
mongod --replSet rs0 --port "$PORT" --bind_ip 127.0.0.1 --dbpath "$DATA" --fork --logpath "$LOG" >/dev/null \
  || fail "mongod did not start"

shell() { mongosh "mongodb://127.0.0.1:$PORT/?directConnection=true" --quiet --eval "$1"; }

for _ in $(seq 60); do shell "db.adminCommand({ping: 1}).ok" >/dev/null 2>&1 && break; sleep 1; done
shell "db.adminCommand({ping: 1}).ok" >/dev/null 2>&1 || fail "mongod did not answer within 60 s"

shell "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'localhost:$PORT'}]}).ok" >/dev/null \
  || fail "rs.initiate failed"
for _ in $(seq 60); do [[ "$(shell 'db.hello().isWritablePrimary' 2>/dev/null)" == "true" ]] && break; sleep 1; done
[[ "$(shell 'db.hello().isWritablePrimary' 2>/dev/null)" == "true" ]] || fail "replica set did not elect a primary within 60 s"

echo "MongoDB replica set rs0 ready on localhost:$PORT"
