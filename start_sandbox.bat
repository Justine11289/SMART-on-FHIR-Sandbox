@echo off
setlocal enabledelayedexpansion

:: Ensure correct directory even if called directly
cd /d "%~dp0"

:: ======================================================
:: Step 0: Docker Environment Check
:: ======================================================
set "COMPOSE_CMD=docker compose"
docker compose version >nul 2>&1 || set "COMPOSE_CMD=docker-compose"

:: Privacy Mode: Lock to domain name instead of IP
set "PUBLIC_HOST=fhir.sandbox.local"
set "PROTOCOL=https"

echo [INFO] Privacy Protection: IP detection skipped.
echo [INFO] Environment locked to: %PUBLIC_HOST%

:: ======================================================
:: Step 1.1: Precision Configuration Sync
:: ======================================================
echo [INFO] Synchronizing configuration files...

:: Sync .env - Using start-of-line anchors for accuracy
powershell -NoProfile -Command ^
    "$envPath='.\.env';" ^
    "$c = Get-Content $envPath;" ^
    "$c = $c -replace '^HOST_IP=.*', 'HOST_IP=fhir.sandbox.local';" ^
    "$c = $c -replace '^PUBLIC_HOST=.*', 'PUBLIC_HOST=fhir.sandbox.local';" ^
    "$c = $c -replace '^HOST=.*', 'HOST=fhir.sandbox.local';" ^
    "$c = $c -replace '^FHIR_SERVER_R4=.*', 'FHIR_SERVER_R4=https://fhir.sandbox.local/fhir/hapi-fhir-jpaserver/fhir';" ^
    "Set-Content $envPath $c"

:: Sync nginx.conf
powershell -NoProfile -Command ^
    "$confPath='.\nginx.conf';" ^
    "(Get-Content $confPath) -replace 'server_name.*;', 'server_name %PUBLIC_HOST%;' | Set-Content $confPath"

:: Sync r4-local.json5 (Forced Relative Paths to fix Mixed Content)
if exist ".\patient-browser\r4-local.json5" (
    powershell -NoProfile -Command ^
        "$jsonPath='.\patient-browser\r4-local.json5';" ^
        "(Get-Content $jsonPath) -replace 'url: .http:.*', 'url: ''/fhir/hapi-fhir-jpaserver/fhir'',' | Set-Content $jsonPath"
)

echo [OK] All configurations synchronized with domain %PUBLIC_HOST%.

:: ======================================================
:: Step 1.2: Certificates and Infrastructure
:: ======================================================
docker network create fhir-network >nul 2>&1

if not exist ".\certs\sandbox.crt" (
    echo [ERROR] TLS Certificate not found in .\certs\sandbox.crt
    pause & exit /b 1
)

echo [INFO] Cleaning environment...
%COMPOSE_CMD% down

:: ======================================================
:: Step 3-6: Sequential Service Launch
:: ======================================================
echo [INFO] Starting Infrastructure (DB/Auth)...
%COMPOSE_CMD% up -d db keycloak

echo [INFO] Waiting for Keycloak initialization (60s)...
timeout /t 60 /nobreak

echo [INFO] Starting Application services...
%COMPOSE_CMD% up -d r4 smart-launcher patient-browser oauth2-proxy

echo [INFO] Activating Nginx Gateway...
%COMPOSE_CMD% up -d nginx
%COMPOSE_CMD% restart nginx

echo.
echo [SUCCESS] SMART-on-FHIR Sandbox is ready!
echo [URL] %PROTOCOL%://%PUBLIC_HOST%/
echo.
pause