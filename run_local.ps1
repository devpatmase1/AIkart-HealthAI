# Healthcare Agent Orchestrator - Local Windows Launcher (PowerShell)
$Host.UI.RawUI.WindowTitle = "Healthcare Agent Orchestrator"
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   Healthcare Agent Orchestrator - Local Windows Launcher" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

$RootPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $RootPath

# Check virtual environment
if (-Not (Test-Path "$RootPath\.venv\Scripts\python.exe")) {
    Write-Host "[ERROR] Virtual environment .venv not found." -ForegroundColor Red
    Write-Host "Please create it using Python 3.10 and install dependencies."
    Read-Host "Press Enter to exit..."
    exit 1
}

# Check .env
if (-Not (Test-Path "$RootPath\.env")) {
    if (Test-Path "$RootPath\.env.example") {
        Write-Host "[INFO] Creating .env from .env.example..." -ForegroundColor Yellow
        Copy-Item "$RootPath\.env.example" "$RootPath\.env"
    }
}

Write-Host "[INFO] Launching Backend Server on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RootPath'; & '$RootPath\.venv\Scripts\Activate.ps1'; `$env:PYTHONPATH='src'; python -m uvicorn app:app --host 127.0.0.1 --port 8000 --app-dir src --reload"

Write-Host "[INFO] Launching Frontend React UI on http://localhost:3000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RootPath\democlient'; npm run dev"

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   Application is starting up!" -ForegroundColor Green
Write-Host "   - Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "   - Frontend UI:  http://localhost:3000" -ForegroundColor White
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close this launcher window..."
