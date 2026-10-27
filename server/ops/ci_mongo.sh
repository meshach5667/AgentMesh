#!/usr/bin/env bash
# Start a single-node MongoDB replica set for CI and wait until it accepts writes (ledger postings need transactions,
# so a replica set is required).
#
#   server/ops/ci_mongo.sh            # then use mongodb://localhost:27017/?replicaSet=rs0
#
# Runs mongod directly on the runner, not in a container. MongoDB 8.0 server, shell and database tools are installed
# from MongoDB's official apt repository unless mongod 7+, mongosh and mongodump are already on PATH. A MongoDB
# service preinstalled on the runner is stopped first so it cannot hold the port. On any failure the script reports
# the failing command, what is listening on the port, and mongod's log.
set -euo pipefail

PORT="${MONGO_PORT:-27017}"
WORK="${RUNNER_TEMP:-/tmp}/agentmesh-mongo"
DATA="$WORK/data"
LOG="$WORK/mongod.log"

diagnose() {
  echo "--- listening on port $PORT ---"
  (ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null || true) | grep ":$PORT " || echo "(nothing)"
  echo "--- mongod log (last 60 lines) ---"
  tail -n 60 "$LOG" 2>/dev/null || echo "(no log)"
}
fail() {
  echo "::error::ci_mongo.sh: $1"
  diagnose
  exit 1
}
trap 'fail "command failed (line $LINENO): $BASH_COMMAND"' ERR

step() { echo "==> $*"; }

mongod_major() {
  # No early-closing pipe (e.g. `| head -1`): with pipefail, mongod could be killed by SIGPIPE and abort the script.
  local out
  out=$(mongod --version 2>/dev/null) || return 0
  sed -n 's/^db version v\([0-9]*\).*/\1/p' <<<"$out"
}

needs_install() {
  command -v mongod >/dev/null 2>&1 || return 0
  command -v mongosh >/dev/null 2>&1 || return 0
  command -v mongodump >/dev/null 2>&1 || return 0
  local major
  major=$(mongod_major)
  [[ -z "$major" || "$major" -lt 7 ]]
}

if needs_install; then
  step "Installing MongoDB 8.0 from repo.mongodb.org"
  # MongoDB publishes complete 8.0 packages (server, mongosh, tools) for jammy and noble only; its repositories for
  # newer releases (e.g. Ubuntu 26.04 "resolute") hold only the database tools. Use noble's packages there.
  codename=$(. /etc/os-release && echo "${VERSION_CODENAME:-noble}")
  case "$codename" in
    jammy | noble) ;;
    *) echo "No complete MongoDB 8.0 packages for Ubuntu '$codename'; using noble's"; codename=noble ;;
  esac
  keyring=/usr/share/keyrings/mongodb-server-8.0.gpg
  curl -fsSL --retry 3 https://pgp.mongodb.com/server-8.0.asc | sudo gpg --batch --yes --dearmor -o "$keyring"
  echo "deb [ arch=amd64,arm64 signed-by=$keyring ] https://repo.mongodb.org/apt/ubuntu ${codename}/mongodb-org/8.0 multiverse" \
    | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list >/dev/null
  sudo apt-get update -q
  sudo apt-get install -y -q --no-install-recommends mongodb-org-server mongodb-mongosh mongodb-database-tools
fi
step "Using mongod $(mongod_major).x, $(command -v mongod)"

# A preinstalled MongoDB service would hold the port.
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet mongod 2>/dev/null; then
  step "Stopping the runner's own mongod service"
  sudo systemctl stop mongod
fi

step "Starting mongod (replica set rs0) on port $PORT"
mkdir -p "$DATA"
mongod --replSet rs0 --port "$PORT" --bind_ip 127.0.0.1 --dbpath "$DATA" --fork --logpath "$LOG" >/dev/null \
  || fail "mongod did not start"

shell() { mongosh "mongodb://127.0.0.1:$PORT/?directConnection=true" --quiet --eval "$1"; }

step "Waiting for mongod"
ready=""
for _ in $(seq 60); do
  if shell "db.adminCommand({ping: 1}).ok" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[[ -n "$ready" ]] || fail "mongod did not answer within 60 s"

step "Initiating the replica set"
shell "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'localhost:$PORT'}]}).ok" >/dev/null || fail "rs.initiate failed"
primary=""
for _ in $(seq 60); do
  if [[ "$(shell 'db.hello().isWritablePrimary' 2>/dev/null || true)" == "true" ]]; then primary=1; break; fi
  sleep 1
done
[[ -n "$primary" ]] || fail "replica set did not elect a primary within 60 s"

trap - ERR
echo "MongoDB replica set rs0 ready on localhost:$PORT"
