#!/usr/bin/env bash
# Nightly snapshot of the job-search state. Installed as a cron job by deploy.sh.
#
# Why this exists on top of whatever backs up the host: a whole-machine image
# restores the machine, not a single bad edit, and it backs up a corrupted
# database just as faithfully as a good one. Once hosted, the profile lives
# only on this server, so a bad AI-written fact or an accidental section
# replace has no other copy. These snapshots are the fine-grained undo.
set -euo pipefail

BASE="${JOBSEARCH_REMOTE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
SRC_DB="${JOBSEARCH_DB:-$BASE/data/jobsearch.db}"
PROFILE="${PROFILE_DIR:-$BASE/profile}"
DEST="${BACKUP_DEST:-$BASE/data/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"

mkdir -p "$DEST"
STAMP="$(date +%Y%m%dT%H%M%S)"

# sqlite3's .backup is safe against a live writer; a plain file copy is not.
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$SRC_DB" ".backup '$DEST/jobsearch.$STAMP.db'"
else
    docker exec jobsearch-mcp python -c "
import sqlite3
s = sqlite3.connect('/data/jobsearch.db')
d = sqlite3.connect('/data/backups/jobsearch.$STAMP.db')
s.backup(d); d.close(); s.close()"
fi

if [ -d "$PROFILE" ]; then
    tar -czf "$DEST/profile.$STAMP.tar.gz" -C "$PROFILE" .
fi

find "$DEST" -name 'jobsearch.*.db'   -mtime +"$KEEP_DAYS" -delete
find "$DEST" -name 'profile.*.tar.gz' -mtime +"$KEEP_DAYS" -delete

echo "$(date -Is) snapshot ok: $(ls -1 "$DEST" | wc -l) files retained"
