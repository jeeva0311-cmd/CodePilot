@echo off
setlocal enabledelayedexpansion

title CodePilot Agent

echo.
echo  =========================================
echo   CodePilot Agent - AI Coding Assistant
echo  =========================================
echo.

:: ── Check Python ─────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Download Python 3.11+ from https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python %PY_VER% found.

:: ── Set working directory to script location ──────────────────────────────────
cd /d "%~dp0"

:: ── Create .env if it doesn't exist ──────────────────────────────────────────
if not exist ".env" (
    echo [INFO] .env not found — copying .env.example to .env
    copy ".env.example" ".env" >nul
    echo.
    echo  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo  !! ACTION REQUIRED: Open .env and add your          !!
    echo  !! OPENAI_API_KEY before the agent can run tasks.   !!
    echo  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
)

:: ── Install / verify dependencies ─────────────────────────────────────────────
echo [INFO] Checking dependencies…
python -c "import fastapi, uvicorn, sqlalchemy, openai, dotenv" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies from requirements.txt…
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed.
) else (
    echo [OK] Dependencies already satisfied.
)

:: ── Start the server ──────────────────────────────────────────────────────────
echo.
echo [INFO] Starting CodePilot Agent backend…
echo [INFO] Open your browser at: http://127.0.0.1:8000
echo [INFO] Press Ctrl+C to stop.
echo.

cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause
