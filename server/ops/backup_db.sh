#!/usr/bin/env bash
# Back up the AgentMesh MongoDB database to a compressed, timestamped archive (mongodump).
#
#   MONGODB_URL=mongodb+srv://user:pass@cluster0.example.mongodb.net/ ops/backup_db.sh /var/backups/agentmesh
#
# Dumps MONGODB_DB (default agentmesh) and keeps the newest $KEEP archives (default 14) in the target directory.
# Set MONGODUMP to use a specific binary, e.g. MONGODUMP="docker run --rm --network host mongo:8.0 mongodump".
# --oplog is not used (it needs a whole-instance dump); stop writes or use Atlas backups for point-in-time copies.
set -euo pipefail

dest="${1:?usage: backup_db.sh <directory>}"
url="${MONGODB_URL:?MONGODB_URL is required}"
db="${MONGODB_DB:-agentmesh}"
keep="${KEEP:-14}"
mongodump="${MONGODUMP:-mongodump}"

mkdir -p "$dest"
umask 077   # archives contain account and ledger data
file="$dest/agentmesh-$(date -u +%Y%m%dT%H%M%SZ).archive.gz"
$mongodump --uri="$url" --db="$db" --gzip --archive > "$file.partial"
mv "$file.partial" "$file"
echo "Wrote $file ($(du -h "$file" | cut -f1))"

ls -1t "$dest"/agentmesh-*.archive.gz 2>/dev/null | tail -n +"$((keep + 1))" | xargs -r rm -f
