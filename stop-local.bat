@echo off
REM ============================================================
REM BGV Platform - Stop All Local Services
REM ============================================================

title BGV Platform - Stopping Services

echo ============================================================
echo  BGV Platform - Stopping All Services
echo ============================================================
echo.

REM --- Stop Frontend (node process on port 3000) ---
echo [1/3] Stopping Frontend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo    Frontend stopped.
echo.

REM --- Stop Backend (uvicorn on port 8000) ---
echo [2/3] Stopping Backend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo    Backend stopped.
echo.

REM --- Stop Ollama ---
echo [3/3] Stopping Ollama...
taskkill /IM ollama.exe /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Ollama" /F >nul 2>&1
echo    Ollama stopped.
echo.

echo ============================================================
echo  All BGV services stopped.
echo  PostgreSQL left running (use 'net stop postgresql-x64-18')
echo ============================================================
echo.
pause
