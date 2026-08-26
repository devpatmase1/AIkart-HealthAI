@echo off
echo =======================================================
echo   Healthcare Agent Orchestrator - Local Windows Launcher
echo =======================================================
echo.

cd /d "%~dp0"

:: Check for virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv not found.
    echo Please create it using Python 3.10 and install dependencies.
    pause
    exit /b 1
)

:: Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creating .env from .env.example...
        copy .env.example .env
    )
)

echo [INFO] Starting Backend Server on http://localhost:8000 ...
start "Healthcare Agent - Backend" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && set PYTHONPATH=src && python -m uvicorn app:app --host 127.0.0.1 --port 8000 --app-dir src --reload"

echo [INFO] Starting Frontend React UI on http://localhost:3000 ...
start "Healthcare Agent - Frontend" cmd /k "cd /d %~dp0democlient && npm run dev"

echo.
echo =======================================================
echo   System running!
echo   - Backend API: http://localhost:8000
echo   - Frontend UI:  http://localhost:3000
echo =======================================================
echo.
pause
