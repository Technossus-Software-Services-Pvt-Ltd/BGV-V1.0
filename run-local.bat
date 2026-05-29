@echo off
REM ============================================================
REM BGV Platform - Local Development Runner (No Docker)
REM Starts: PostgreSQL, Ollama, Backend, Frontend
REM Config is loaded from backend/.env and frontend/.env
REM ============================================================

title BGV Platform - Local Dev

echo ============================================================
echo  BGV Platform - Starting Local Services
echo ============================================================
echo.

REM --- Step 1: Start PostgreSQL ---
echo [1/3] Starting PostgreSQL...
net start postgresql-x64-18 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo    PostgreSQL service started.
) else (
    echo    PostgreSQL already running.
)
echo.

REM --- Step 2: Start Ollama ---
echo [2/3] Starting Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if %ERRORLEVEL% neq 0 (
    start "Ollama" /min cmd /c "ollama serve"
    timeout /t 3 /nobreak >nul
    echo    Ollama started.
) else (
    echo    Ollama already running.
)
echo.

REM --- Step 3: Start Backend and Frontend ---
echo [3/3] Starting Backend and Frontend...
echo.
echo    Backend:  http://localhost:8000
echo    Frontend: http://localhost:3000
echo    API Docs: http://localhost:8000/docs
echo.
echo ============================================================
echo  All services running. Close terminal windows to stop.
echo ============================================================
echo.

REM Start backend in a new window (reads config from backend/.env)
cd /d %~dp0backend
start "BGV Backend" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

REM Start frontend in a new window (reads config from frontend/.env)
cd /d %~dp0frontend
start "BGV Frontend" cmd /k "npm run dev"

echo.
echo All services launched in separate windows.
pause >nul
