# scripts/ragop.ps1
# Wrapper to run the RagOp CLI via the repo's local venv without manual activation.
# Usage examples:
#   .\scripts\ragop.ps1 build K:\Repos\RagOp
#   .\scripts\ragop.ps1 query "test retrieval"
#   .\scripts\ragop.ps1 compose "How to use?" --k 1

[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$ErrorActionPreference = 'Stop'

# Resolve paths
$ScriptDir = Split-Path -LiteralPath $PSCommandPath -Parent
$Root      = Split-Path -LiteralPath $ScriptDir -Parent
$Venv      = Join-Path $Root '.venv'

if (-not (Test-Path $Venv)) {
  Write-Error "Virtual env not found: $Venv. Run scripts/setup.ps1 first."
  exit 1
}

# Prefer console entrypoint if installed; fallback to python -m ragop.cli
$ExeRagop = Join-Path $Venv 'Scripts\ragop.exe'
$ExePy    = Join-Path $Venv 'Scripts\python.exe'

if (Test-Path $ExeRagop) {
  & $ExeRagop @Args
  exit $LASTEXITCODE
}
elseif (Test-Path $ExePy) {
  & $ExePy -m ragop.cli @Args
  exit $LASTEXITCODE
}
else {
  Write-Error "Neither ragop.exe nor python.exe found in $($Venv)\Scripts. Re-run scripts/setup.ps1."
  exit 1
}