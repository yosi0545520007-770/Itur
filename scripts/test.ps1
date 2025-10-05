$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

$venvPy = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Error "Virtualenv not found. Run ./scripts/setup.ps1 first."
}

& $venvPy -m pytest -q

