$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

$venvPy = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Error -Message "לא נמצאה סביבה וירטואלית. הרץ ./scripts/setup.ps1 קודם."
}

# הרצת אפליקציית Streamlit
& $venvPy -m streamlit run app.py
