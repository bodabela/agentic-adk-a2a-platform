@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

title Agent Platform (DEV)

:: ---- Project selection (default: personal_assistant) ----
if "%APP_PROJECT%"=="" set "APP_PROJECT=personal_assistant"

echo.
echo ============================================
echo   Agent Platform - Dev Mode (Hot Reload)
echo   Project: %APP_PROJECT%
echo ============================================
echo.

:: ---- Docker check ----
echo [1/4] Checking Docker ...
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

:: ---- Project directory check ----
if not exist "%ROOT%\projects\%APP_PROJECT%" (
    echo   [FAIL] Project "%APP_PROJECT%" not found in projects\ directory.
    echo          Available projects:
    for /d %%D in ("%ROOT%\projects\*") do echo            - %%~nxD
    pause
    exit /b 1
)
echo   [OK]   Project "%APP_PROJECT%" found

:: ---- .env check ----
echo [2/4] Checking .env ...
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

:: ---- Clean Langfuse trace data (keep Postgres for org/project/keys) ----
echo [3/4] Cleaning Langfuse traces ...
pushd "%ROOT%"
docker compose rm -sfv langfuse langfuse-worker langfuse-clickhouse langfuse-redis langfuse-minio >nul 2>&1
for %%V in (langfuse-clickhouse-data langfuse-clickhouse-logs langfuse-redis-data langfuse-minio-data) do (
    docker volume rm "agentic-adk-a2a-platform_%%V" >nul 2>&1
)
echo   [OK]   Langfuse traces cleaned (org/keys preserved)
popd

:: ---- Build & Start (dev mode with override) ----
echo [4/4] Starting services in DEV mode ...
echo.

pushd "%ROOT%"
docker compose up --build --force-recreate -d
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
echo   Dev services running (hot reload active)
echo ============================================
echo.
echo   Frontend:     http://localhost:5173
echo   Backend API:  http://localhost:8000
echo   Swagger UI:   http://localhost:8000/docs
echo   SSE Stream:   http://localhost:8000/api/events/stream
echo.
echo   Observability:
echo     Grafana:      http://localhost:3002  (admin/admin)
echo     Prometheus:   http://localhost:9090
echo     Langfuse:     http://localhost:3001
echo     Tempo:        http://localhost:3200
echo.
echo   Hot reload:
echo     - Backend:  edit backend/src/ ^-^> uvicorn auto-restarts
echo     - Frontend: edit frontend/src/ ^-^> Vite HMR refreshes browser
echo.
echo   Logs:         docker compose logs -f
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
