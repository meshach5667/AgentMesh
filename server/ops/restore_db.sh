#!/usr/bin/env bash
# Restore an archive made by backup_db.sh into an EMPTY database.
#
#   MONGODB_URL=mongodb://127.0.0.1:27017/?replicaSet=rs0 MONGODB_DB=agentmesh_restore \
#     ops/restore_db.sh agentmesh-....archive.gz
#
# Restore into a new database and point the API at it (MONGODB_DB) after checking it; never restore over a live one.
# The API creates any missing collections and indexes at startup. Afterwards GET /api/v1/admin/reconciliation to
# confirm the ledger is consistent.
set -euo pipefail

file="${1:?usage: restore_db.sh <archive>}"
url="${MONGODB_URL:?MONGODB_URL is required}"
db="${MONGODB_DB:?MONGODB_DB is required (the database to restore into)}"
mongorestore="${MONGORESTORE:-mongorestore}"
mongosh="${MONGOSH:-mongosh}"

count=$($mongosh "$url" --quiet --eval "db.getSiblingDB('$db').getCollectionNames().length")
if [ "$count" != "0" ]; then
  echo "Refusing to restore: database $db is not empty ($count collections)." >&2
  exit 1
fi
# Archives hold the source database name (agentmesh); --nsFrom/--nsTo rename it to the target.
# The archive is read from stdin, so MONGORESTORE may be a container without access to the file.
$mongorestore --uri="$url" --gzip --archive --nsFrom="agentmesh.*" --nsTo="$db.*" --stopOnError < "$file"
echo "Restored $file into $db"
