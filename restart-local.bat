@echo off
REM ============================================================
REM BGV Platform - Restart All Local Services
REM ============================================================

title BGV Platform - Restarting Services

echo ============================================================
echo  BGV Platform - Restarting All Services
echo ============================================================
echo.

REM --- Stop all services first ---
echo Stopping services...
echo.

REM Stop Frontend
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM Stop Backend
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM Stop Ollama
taskkill /IM ollama.exe /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Ollama" /F >nul 2>&1

echo All services stopped.
echo.
timeout /t 2 /nobreak >nul

REM --- Now start everything via run-local.bat ---
echo Restarting...
echo.
call "%~dp0run-local.bat"
