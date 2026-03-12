@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

title Agent Platform

echo.
echo ============================================
echo   Agent Platform - Docker Startup
echo ============================================
echo.

:: ---- Docker check ----
echo [1/3] Checking Docker ...
where docker >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Docker daemon is not running. Start Docker Desktop and try again.
    pause
    exit /b 1
)
echo   [OK]   Docker available

:: ---- .env check ----
echo [2/3] Checking .env ...
if not exist "%ROOT%\.env" (
    if exist "%ROOT%\.env.example" (
        copy "%ROOT%\.env.example" "%ROOT%\.env" >nul
        echo   [WARN] .env created from .env.example
        echo   [!]    Edit .env and set your API keys before using LLM features.
    ) else (
        echo   [FAIL] .env not found and no .env.example available.
        pause
        exit /b 1
    )
) else (
    echo   [OK]   .env found
)

:: ---- Build & Start ----
echo [3/3] Starting services with Docker Compose ...
echo.

pushd "%ROOT%"
docker compose up --build -d
if errorlevel 1 (
    echo.
    echo   [FAIL] Docker Compose failed. Check the output above for errors.
    popd
    pause
    exit /b 1
)
popd

:: ---- Wait for health ----
echo.
echo Waiting for backend health check ...
set "TRIES=0"
:wait_backend
timeout /t 2 /nobreak >nul
set /a TRIES+=1
curl -s -o nul http://127.0.0.1:8000/health 2>nul
if not errorlevel 1 goto :ready
if !TRIES! GEQ 15 (
    echo   [WARN] Backend not healthy after 30s - check logs: docker compose logs backend
    goto :show_urls
)
goto :wait_backend

:ready
echo   [OK]   Backend healthy

:: ============================================
::  Ready
:: ============================================

:show_urls
echo.
echo ============================================
echo   All services running!
echo ============================================
echo.
echo   Frontend:     http://localhost:3000
echo   Backend API:  http://localhost:8000
echo   Swagger UI:   http://localhost:8000/docs
echo   SSE Stream:   http://localhost:8000/api/events/stream
echo.
echo   Logs:         docker compose logs -f
echo   Agents run in-process (no separate service needed).
echo.
echo   Press any key to STOP all services ...
echo.
pause >nul

:: ============================================
::  Shutdown
:: ============================================

echo.
echo Stopping services ...
pushd "%ROOT%"
docker compose down
popd

echo Done.
endlocal
