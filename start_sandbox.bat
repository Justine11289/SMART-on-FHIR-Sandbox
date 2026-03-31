@echo off
setlocal enabledelayedexpansion

set "COMPOSE_CMD=docker compose"
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    docker-compose version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Docker Compose was not found. Install Docker Desktop and retry.
        pause
        exit /b 1
    )
    set "COMPOSE_CMD=docker-compose"
)

echo [INFO] Step 1: Detecting network IP...
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|Pseudo|VirtualBox|VMware|WSL' -and $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' } | Select-Object -ExpandProperty IPAddress -First 1"`) do set CLEAN_IP=%%i

if "%CLEAN_IP%"=="" (
    echo [ERROR] Could not detect a valid local IP.
    pause
    exit /b
)
echo [INFO] Detected IP: %CLEAN_IP%

echo [INFO] Compose command: %COMPOSE_CMD%

echo [INFO] Step 1.1: Ensuring required docker network exists...
docker network inspect fhir-network >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Creating docker network: fhir-network
    docker network create fhir-network >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create docker network fhir-network.
        pause
        exit /b 1
    )
)

:: Update config files with detected IP
powershell -NoProfile -Command "(Get-Content .env) -replace 'HOST_IP=.*', 'HOST_IP=%CLEAN_IP%' -replace 'HOST=.*', 'HOST=%CLEAN_IP%' | Set-Content .env"
powershell -NoProfile -Command "(Get-Content nginx.conf) -replace 'server_name.*;', 'server_name %CLEAN_IP%;' | Set-Content nginx.conf"

echo [INFO] Step 2: Cleaning environment...
%COMPOSE_CMD% down

echo [INFO] Step 3: Starting Keycloak and Database...
%COMPOSE_CMD% up -d db keycloak

echo [INFO] Step 4: Waiting for Keycloak to be READY...
set /a RETRIES=0
:WAIT_KEYCLOAK
docker exec keycloak bash -lc "echo > /dev/tcp/127.0.0.1/8180" 2>nul
if %errorlevel% neq 0 (
    set /a RETRIES+=1
    if !RETRIES! geq 30 (
        echo [ERROR] Keycloak was not ready after 5 minutes.
        echo [HINT] Check logs with: docker logs keycloak --tail 200
        pause
        exit /b 1
    )
    echo [WAIT] Keycloak is still starting...
    timeout /t 10 /nobreak >nul
    goto WAIT_KEYCLOAK
)
echo [OK] Keycloak is UP and LISTENING

echo [INFO] Step 5: Starting remaining services...
%COMPOSE_CMD% up -d r4 smart-launcher patient-browser oauth2-proxy

echo [INFO] Step 6: Starting Nginx Gateway...
%COMPOSE_CMD% up -d nginx
%COMPOSE_CMD% restart nginx

echo.
echo [SUCCESS] Sandbox startup sequence completed
echo [CHECK] Launcher:       http://%CLEAN_IP%/
echo [CHECK] FHIR Metadata:  http://%CLEAN_IP%/fhir/hapi-fhir-jpaserver/fhir/metadata
echo [NOTE] Use the IP-based URLs above (do not use localhost) to avoid OAuth cookie/callback issues.
echo.
pause