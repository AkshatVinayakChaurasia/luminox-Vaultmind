Set-Location $PSScriptRoot
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --upgrade pip
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}
Write-Host ""
Write-Host "VaultMind - Sovereign AI Workbench (Team Luminox)" -ForegroundColor Cyan
Write-Host "  Landing : http://127.0.0.1:8080/"
Write-Host "  Console : http://127.0.0.1:8080/console"
Write-Host ""
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080
