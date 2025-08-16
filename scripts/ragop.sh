#!/usr/bin/env bash
# Wrapper to run the ragop CLI via the local venv without manual activation.
# Usage examples:
#   scripts/ragop.sh build .
#   scripts/ragop.sh query "search terms"
#   scripts/ragop.sh compose "question"

set -euo pipefail

# Resolve repo root (works on Linux/macOS/WSL)
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"

VENV="$REPO_ROOT/.venv"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
  echo "Error: Python venv not found at $VENV"
  echo "Run: scripts/setup.sh"
  exit 1
fi

# Prefer module invocation to avoid PATH issues with console scripts
exec "$PY" -m ragop.cli "$@"