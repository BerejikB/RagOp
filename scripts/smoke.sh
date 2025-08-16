#!/usr/bin/env bash
set -euo pipefail

# Smoke test for RagOp: setup venv, build index, run query + compose

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.."; pwd)"
cd "$ROOT"

# Config defaults (can be overridden by env before calling this script)
: "${RAGOP_INDEX:="$ROOT/.index/rag_index.pkl"}"
: "${RAGOP_K:=1}"
: "${RAGOP_SNIPPET_MAX_CHARS:=500}"
: "${RAGOP_MAX_TOTAL_CHARS:=1200}"

echo "[smoke] repo: $ROOT"
echo "[smoke] index: $RAGOP_INDEX"

# Ensure .sh files have LF endings and are executable (best-effort)
if command -v dos2unix >/dev/null 2>&1; then
  find "$ROOT/scripts" -maxdepth 1 -type f -name "*.sh" -print0 2>/dev/null | xargs -0 -r dos2unix -q || true
fi
chmod +x "$ROOT/scripts/"*.sh 2>/dev/null || true

# Create venv + install package if missing
if [ ! -d "$ROOT/.venv" ]; then
  echo "[smoke] venv missing -> running setup.sh"
  "$ROOT/scripts/setup.sh"
fi

# Build index
echo "[smoke] building index..."
"$ROOT/scripts/ragop.sh" build "$ROOT" --index "$RAGOP_INDEX"

# Query
echo "[smoke] querying..."
"$ROOT/scripts/ragop.sh" query "smoke test query" --k "${RAGOP_K}"

# Compose (ultra-compact by default via env/defaults)
echo "[smoke] composing..."
"$ROOT/scripts/ragop.sh" compose "What is the config precedence?" \
  --k "${RAGOP_K}"

echo "[smoke] OK"