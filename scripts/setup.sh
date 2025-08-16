#!/usr/bin/env bash
set -euo pipefail

# RagOp setup: create local venv and install package in editable mode
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "RagOp setup starting in: $ROOT"

# Find a Python interpreter
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/devnull 2>&1; then
  PY=python
else
  echo "Error: Python not found on PATH. Install Python 3.9+ and retry." >&2
  exit 1
fi

VENV="$ROOT/.venv"

# Create venv if missing
if [ ! -d "$VENV" ]; then
  echo "Creating virtual environment at: $VENV"
  "$PY" -m venv "$VENV"
else
  echo "Virtual environment already exists: $VENV"
fi

# Resolve venv python (Linux/macOS/WSL vs Git-Bash on Windows)
if [ -x "$VENV/bin/python" ]; then
  VPY="$VENV/bin/python"
elif [ -x "$VENV/Scripts/python.exe" ]; then
  VPY="$VENV/Scripts/python.exe"
else
  echo "Error: venv Python not found under $VENV." >&2
  exit 1
fi

echo "Upgrading pip/setuptools/wheel..."
"$VPY" -m pip install --upgrade pip setuptools wheel

echo "Installing RagOp in editable mode..."
"$VPY" -m pip install -e "$ROOT"

# Normalize shell scripts to LF and set executable bit (best-effort)
if [ -d "$ROOT/scripts" ]; then
  if command -v sed >/dev/null 2>&1; then
    find "$ROOT/scripts" -maxdepth 1 -type f -name "*.sh" -print0 \
      | xargs -0 -I{} sh -c 'sed -i "s/\r$//" "$1"' _ {}
  fi
  chmod +x "$ROOT/scripts/"*.sh 2>/dev/null || true
fi

echo "Setup complete."
echo "Tip: run \"$ROOT/scripts/ragop.sh --help\" to use the CLI via the venv."