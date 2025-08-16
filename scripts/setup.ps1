# Creates a local venv and installs RagOp in editable mode
# Usage: scripts\setup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Repo root (scripts is at <repo>\scripts)
$Repo = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Repo '.venv'
$Py   = Join-Path $Venv 'Scripts\python.exe'

Write-Host "Repo: $Repo"
Write-Host "Venv: $Venv"

if (-not (Test-Path $Venv)) {
  Write-Host "Creating venv..."
  python -m venv $Venv
} else {
  Write-Host "Venv already exists, skipping creation."
}

if (-not (Test-Path $Py)) {
  throw "Python not found in venv: $Py"
}

& $Py -m pip install -U pip setuptools wheel
& $Py -m pip install -e $Repo

Write-Host "Done. Use scripts\\ragop.ps1 to run the CLI."
Write-Host "Examples:"
Write-Host "  scripts\\ragop.ps1 build ."
Write-Host "  scripts\\ragop.ps1 query \"compose_ultra_compact\""
Write-Host "  scripts\\ragop.ps1 compose --ultra-compact \"How to use RagOp?\""