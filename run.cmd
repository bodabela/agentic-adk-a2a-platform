@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "ERR=0"
set "TMPVER=%TEMP%\agentplatform_ver.txt"

title Agent Platform

echo.
echo ============================================
echo   Agent Platform - Startup
echo ============================================
echo.

:: ---- Python check ----
echo [1/6] Checking Python ...
where python >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Python not found. Install Python 3.12+ from https://python.org
    set "ERR=1"
    goto :preflight_done
)
python --version > "%TMPVER%" 2>&1
set /p PYVER=<"%TMPVER%"
echo   [OK]   %PYVER%

:: ---- Node.js check ----
echo [2/6] Checking Node.js ...
where node >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Node.js not found. Install from https://nodejs.org
    set "ERR=1"
    goto :preflight_done
)
node --version > "%TMPVER%" 2>&1
set /p NODEVER=<"%TMPVER%"
echo   [OK]   Node.js %NODEVER%

:: ---- pnpm check ----
echo [3/6] Checking pnpm ...
where pnpm >nul 2>&1
if errorlevel 1 (
    echo   [WARN] pnpm not found - installing via npm ...
    call npm install -g pnpm >nul 2>&1
    where pnpm >nul 2>&1
    if errorlevel 1 (
        echo   [FAIL] Could not install pnpm. Run manually: npm install -g pnpm
        set "ERR=1"
        goto :preflight_done
    )
)
call pnpm --version > "%TMPVER%" 2>&1
set /p PNPMVER=<"%TMPVER%"
echo   [OK]   pnpm %PNPMVER%

:: ---- curl check ----
echo [4/6] Checking curl ...
where curl >nul 2>&1
if errorlevel 1 (
    echo   [WARN] curl not found - health checks will be skipped
    set "NOCURL=1"
) else (
    echo   [OK]   curl available
    set "NOCURL=0"
)

:: ---- .env check ----
echo [5/6] Checking .env ...
if not exist "%ROOT%\.env" (
    if exist "%ROOT%\.env.example" (
        copy "%ROOT%\.env.example" "%ROOT%\.env" >nul
        echo   [WARN] .env created from .env.example
        echo   [!]    Edit .env and set GOOGLE_API_KEY before using LLM features.
    ) else (
        echo   [FAIL] .env not found and no .env.example available.
        set "ERR=1"
    )
) else (
    echo   [OK]   .env found
)
if exist "%ROOT%\.env" (
    findstr /C:"your-gemini-api-key-here" "%ROOT%\.env" >nul 2>&1
    if not errorlevel 1 (
        echo   [WARN] GOOGLE_API_KEY is still placeholder - update it in .env
    )
)

:preflight_done
del "%TMPVER%" >nul 2>&1
if "!ERR!"=="1" (
    echo.
    echo   Prerequisites check failed. Fix the issues above and try again.
    pause
    exit /b 1
)

:: ============================================
::  Install Dependencies
:: ============================================

echo.
echo [6/6] Installing dependencies ...
echo   Installing backend (pip) - this may take a few minutes on first run ...
pushd "%ROOT%\backend"
pip install -e ".[dev]"
popd
echo   [OK]   Backend ready

echo   Installing frontend (pnpm) ...
pushd "%ROOT%\frontend"
call pnpm install
popd
echo   [OK]   Frontend ready

:: ============================================
::  Copy .env
:: ============================================

if not exist "%ROOT%\backend\.env" (
    copy "%ROOT%\.env" "%ROOT%\backend\.env" >nul 2>&1
)

:: ============================================
::  Start Services
:: ============================================

echo.
echo ============================================
echo   Starting services ...
echo ============================================
echo.

:: ---- Backend ----
echo [1/3] Starting backend on :8000 ...
start "AgentPlatform-Backend" /D "%ROOT%\backend" cmd /c "uvicorn src.main:app --reload --host 127.0.0.1 --port 8000"

if "!NOCURL!"=="1" (
    echo   [SKIP] No curl - waiting 5s instead of health check ...
    timeout /t 5 /nobreak >nul
    goto :backend_ok
)
set "TRIES=0"
:wait_backend
timeout /t 2 /nobreak >nul
set /a TRIES+=1
curl -s -o nul http://127.0.0.1:8000/health 2>nul
if not errorlevel 1 goto :backend_ok
if !TRIES! GEQ 10 (
    echo   [FAIL] Backend did not start within 20 seconds.
    echo          Check the AgentPlatform-Backend window for errors.
    pause
    exit /b 1
)
goto :wait_backend

:backend_ok
echo   [OK]   Backend running    http://localhost:8000

:: ---- Coder Agent (A2A) ----
echo [2/3] Starting coder_agent on :8001 ...
start "AgentPlatform-CoderAgent" /D "%ROOT%" cmd /c "uvicorn modules.coder_agent.agent.serve_a2a:app --host 127.0.0.1 --port 8001"

if "!NOCURL!"=="1" (
    timeout /t 3 /nobreak >nul
    goto :agent_ok
)
set "TRIES=0"
:wait_agent
timeout /t 2 /nobreak >nul
set /a TRIES+=1
curl -s -o nul http://127.0.0.1:8001/health 2>nul
if not errorlevel 1 goto :agent_ok
if !TRIES! GEQ 5 (
    echo   [WARN] Coder agent did not respond - continuing anyway.
    goto :start_frontend
)
goto :wait_agent

:agent_ok
echo   [OK]   Coder Agent       http://localhost:8001

:: ---- Frontend ----
:start_frontend
echo [3/3] Starting frontend on :5173 ...
start "AgentPlatform-Frontend" /D "%ROOT%\frontend" cmd /c "call pnpm dev"

if "!NOCURL!"=="1" (
    timeout /t 5 /nobreak >nul
    goto :all_done
)
set "TRIES=0"
:wait_frontend
timeout /t 2 /nobreak >nul
set /a TRIES+=1
curl -s -o nul http://127.0.0.1:5173 2>nul
if not errorlevel 1 goto :frontend_ok
if !TRIES! GEQ 8 (
    echo   [WARN] Frontend did not respond within 16s - may still be starting.
    goto :all_done
)
goto :wait_frontend

:frontend_ok
echo   [OK]   Frontend          http://localhost:5173

:: ============================================
::  Ready
:: ============================================

:all_done
echo.
echo ============================================
echo   All services running!
echo ============================================
echo.
echo   Frontend:     http://localhost:5173
echo   Backend API:  http://localhost:8000
echo   Swagger UI:   http://localhost:8000/docs
echo   SSE Stream:   http://localhost:8000/api/events/stream
echo   Coder Agent:  http://localhost:8001
echo.
echo   Press any key to STOP all services ...
echo.
pause >nul

:: ============================================
::  Shutdown
:: ============================================

echo.
echo Stopping services ...

:: Kill by port - /T kills the entire process tree (needed for uvicorn --reload child processes)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /T /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    taskkill /T /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /T /F /PID %%a >nul 2>&1
)

:: Close the cmd windows too (fallback)
taskkill /FI "WINDOWTITLE eq AgentPlatform-Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AgentPlatform-CoderAgent*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AgentPlatform-Frontend*" /T /F >nul 2>&1

echo Done.
endlocal
