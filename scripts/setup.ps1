$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

function Find-PythonCandidate {
    # מנסה למצוא python במקומות נפוצים — מעדיף התקנות אמיתיות על פני WindowsApps
    $cands = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
    )
    foreach ($p in $cands) { if (Test-Path $p) { return $p } }
    if (Get-Command py -ErrorAction SilentlyContinue) { return (Get-Command py).Source }
    if (Get-Command python -ErrorAction SilentlyContinue) { return (Get-Command python).Source }
    $wa = "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"
    if (Test-Path $wa) { return $wa }
    return $null
}

function New-Venv {
    $py = Find-PythonCandidate
    if (-not $py) { throw "Python not found. Install Python 3.10+ and add to PATH." }
    Write-Host "Creating virtual env with: $py" -ForegroundColor Yellow
    & $py -m venv .venv
}

$venvPy = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $venvPy)) { New-Venv }

# המתנה קצרה עד שיופיע הקובץ
for ($i=0; $i -lt 10 -and -not (Test-Path $venvPy); $i++) { Start-Sleep -Milliseconds 300 }
if (-not (Test-Path $venvPy)) { throw "Virtualenv python.exe not found at $venvPy" }

& $venvPy -m pip install --upgrade pip

# Activate the environment and then install dependencies
Write-Host "Installing project dependencies..." -ForegroundColor Yellow
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '$root\.venv\Scripts\Activate.ps1'; pip install --force-reinstall -e ."

Write-Host "Setup complete. Activate: .\\.venv\\Scripts\\Activate.ps1" -ForegroundColor Green
