#!/usr/bin/env bash
# Deploy the job search MCP server to a host you control over SSH.
#
# Usage:
#   ./deploy.sh user@host                    deploy code + portals
#   ./deploy.sh user@host --pull-profile     copy the server's profile into this repo
#   ./deploy.sh user@host --seed-profile     push this repo's profile TO the server
#
# Override the remote directory with JOBSEARCH_REMOTE_DIR (default ~/jobsearch).
#
# PROFILE OWNERSHIP: once hosted, the SERVER is the source of truth for the
# candidate profile, because it can be edited from a phone via MCP tools. A
# normal deploy therefore does NOT push this repo's copies over it - doing so
# would silently destroy any edit made since the last deploy. Seed once, then
# pull.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_SRC="$REPO_ROOT/.claude/skills/job-application-assistant"
REMOTE_DIR="${JOBSEARCH_REMOTE_DIR:-jobsearch}"

HOST=""
MODE="deploy"
for arg in "$@"; do
  case "$arg" in
    --pull-profile) MODE="pull" ;;
    --seed-profile) MODE="seed" ;;
    --help|-h)      sed -n '2,12p' "$0"; exit 0 ;;
    -*)             echo "unknown option: $arg" >&2; exit 2 ;;
    *)              HOST="$arg" ;;
  esac
done

if [[ -z "$HOST" ]]; then
  echo "error: no target host given." >&2
  echo "usage: ./deploy.sh user@host [--pull-profile|--seed-profile]" >&2
  exit 2
fi

for cmd in ssh rsync; do
  command -v "$cmd" >/dev/null || { echo "error: $cmd is required" >&2; exit 1; }
done

cd "$REPO_ROOT/mcp_server"

if [[ "$MODE" == "pull" ]]; then
  echo "==> pulling profile from $HOST into this repo"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  rsync -az "$HOST:$REMOTE_DIR/profile/" "$tmp/"
  for f in "$tmp"/0*.md; do
    [[ -e "$f" ]] && cp "$f" "$PROFILE_SRC/$(basename "$f")"
  done
  [[ -e "$tmp/CLAUDE.md" ]] && cp "$tmp/CLAUDE.md" "$REPO_ROOT/CLAUDE.md"
  [[ -e "$tmp/StarExamples.md" ]] && cp "$tmp/StarExamples.md" \
      "$REPO_ROOT/documents/interview/StarExamples.md"
  echo "==> done. Review with: git diff"
  exit 0
fi

echo "==> staging portal CLIs"
rm -rf portals
mkdir -p portals
for skill in "$REPO_ROOT"/.agents/skills/*/; do
  [[ -f "$skill/SKILL.md" ]] && cp -R "$skill" portals/
done

echo "==> creating remote directories"
ssh -n "$HOST" "mkdir -p '$REMOTE_DIR'/{data,profile,config}"

if [[ "$MODE" == "seed" ]]; then
  echo "==> SEEDING profile from repo (overwrites any server-side edits)"
  tmp_profile="$(mktemp -d)"
  trap 'rm -rf "$tmp_profile"' EXIT
  cp "$PROFILE_SRC"/0*.md "$tmp_profile/" 2>/dev/null || true
  cp "$REPO_ROOT/CLAUDE.md" "$tmp_profile/" 2>/dev/null || true
  cp "$REPO_ROOT/documents/interview/StarExamples.md" "$tmp_profile/" 2>/dev/null || true
  rsync -az "$tmp_profile/" "$HOST:$REMOTE_DIR/profile/"
else
  echo "==> profile left untouched (server owns it; --seed-profile to overwrite)"
fi

if [[ -f "$REPO_ROOT/jobsearch.config.json" ]]; then
  echo "==> syncing jobsearch.config.json"
  rsync -az "$REPO_ROOT/jobsearch.config.json" "$HOST:$REMOTE_DIR/config/"
else
  echo "==> no jobsearch.config.json found; server will use neutral defaults"
fi

echo "==> syncing code"
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude 'node_modules' \
  --exclude '.env' \
  "$REPO_ROOT/pyproject.toml" "$REPO_ROOT/README.md" \
  "$HOST:$REMOTE_DIR/"
rsync -az --delete --exclude '__pycache__' \
  "$REPO_ROOT/mcp_server/jobsearch_mcp" \
  "$HOST:$REMOTE_DIR/mcp_server/"
rsync -az --delete \
  Dockerfile docker-compose.yml portals \
  "$HOST:$REMOTE_DIR/mcp_server/"
# Compose is invoked from the repo root on the remote side, so the build
# context matches the Dockerfile's COPY paths.
rsync -az docker-compose.yml "$HOST:$REMOTE_DIR/mcp_server/"

echo "==> installing nightly backup"
rsync -az backup.sh "$HOST:$REMOTE_DIR/"
ssh -n "$HOST" "chmod +x '$REMOTE_DIR/backup.sh' && \
  ( crontab -l 2>/dev/null | grep -v 'jobsearch/backup.sh' ; \
    echo '17 2 * * * $REMOTE_DIR/backup.sh >> $REMOTE_DIR/data/backup.log 2>&1' ) | crontab -"

echo "==> building and starting"
ssh -n "$HOST" "cd '$REMOTE_DIR/mcp_server' && docker compose up -d --build"
ssh -n "$HOST" "cd '$REMOTE_DIR/mcp_server' && docker compose ps --format '{{.Name}}\t{{.Status}}'"
echo "==> done"
