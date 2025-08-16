#!/usr/bin/env bash
set -euo pipefail

# setup.sh — Create a local venv and install RagOp in editable mode.
# Usage: bash scripts/setup.sh
# Env overrides:
#   PYTHON: path/name of Python (default: auto-detect python3/python)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd -P)"
VENV_DIR="${REPO_ROOT}/.venv"

# Pick a Python
PYTHON_BIN="${PYTHON:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Error: Python 3 not found. Install Python 3.9+ and re-run." >&2
    exit 1
  fi
fi

echo "Repo: ${REPO_ROOT}"
echo "Venv: ${VENV_DIR}"
echo "Python: ${PYTHON_BIN}"
echo

# Create venv
"${PYTHON_BIN}" -m venv "${VENV_DIR}"

# Normalize LF endings for .sh files (helps on Windows checkouts)
if command -v dos2unix >/dev/null 2>&1; then
  dos2unix -q "${REPO_ROOT}/scripts/"*.sh || true
else
  sed -i 's/\r$//' "${REPO_ROOT}/scripts/"*.sh 2>/dev/null || true
fi

# Upgrade packaging tools
"${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel

# Install RagOp in editable mode
"${VENV_DIR}/bin/pip" install -e "${REPO_ROOT}"

# Ensure bash wrapper is executable
chmod +x "${REPO_ROOT}/scripts/ragop.sh" 2>/dev/null || true

echo
echo "RagOp setup complete."
echo "Next steps:"
echo "  • Linux/macOS/WSL: ${REPO_ROOT}/scripts/ragop.sh --help"
echo "  • Windows PowerShell: scripts\\setup.ps1 (then run scripts\\ragop.ps1 --help)"