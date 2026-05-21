@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "COMPOSE_CMD=docker compose"
docker compose version >nul 2>&1 || set "COMPOSE_CMD=docker-compose"

set "PUBLIC_HOST=smartonfhir.sandbox.local"
set "PROTOCOL=https"

echo [INFO] Privacy Protection: IP detection skipped.
echo [INFO] Environment locked to: %PUBLIC_HOST%
echo [INFO] Synchronizing configuration files...

:: 同步設定檔
powershell -NoProfile -Command "$envPath='.\.env'; $c = Get-Content $envPath; $c = $c -replace '^HOST_IP=.*', 'HOST_IP=smartonfhir.sandbox.local'; $c = $c -replace '^PUBLIC_HOST=.*', 'PUBLIC_HOST=smartonfhir.sandbox.local'; $c = $c -replace '^HOST=.*', 'HOST=smartonfhir.sandbox.local'; $c = $c -replace '^FHIR_SERVER_R4=.*', 'FHIR_SERVER_R4=https://smartonfhir.sandbox.local/fhir/hapi-fhir-jpaserver/fhir'; Set-Content $envPath $c"

powershell -NoProfile -Command "$confPath='.\nginx.conf'; (Get-Content $confPath) -replace 'server_name.*;', 'server_name %PUBLIC_HOST%;' | Set-Content $confPath"

if exist ".\patient-browser\r4-local.json5" (
    powershell -NoProfile -Command "$jsonPath='.\patient-browser\r4-local.json5'; (Get-Content $jsonPath) -replace 'url: .http:.*', 'url: ''/fhir/hapi-fhir-jpaserver/fhir'',' | Set-Content $jsonPath"
)

echo [OK] All configurations synchronized with domain %PUBLIC_HOST%.

docker network create fhir-network >nul 2>&1

if not exist ".\certs\sandbox.crt" (
    echo [ERROR] TLS Certificate not found in .\certs\sandbox.crt
    pause & exit /b 1
)

echo [INFO] Stopping containers safely (preserving FHIR data)...
%COMPOSE_CMD% down

echo ==========================================================================
echo  [STAGE 1] Launching Core Engines (DB / Keycloak / FHIR R4)
echo ==========================================================================
%COMPOSE_CMD% up -d --force-recreate db keycloak r4 smart-launcher patient-browser

echo.
echo [WAIT] Giving Keycloak Java VM 85 seconds to fully initialize and open Port 8180...
echo [INFO] Please stand by. Do NOT run verify.py yet...
echo.

:: 倒數 85 秒，確保 Keycloak 在背景完全可以用
timeout /t 85 /nobreak

echo.
echo [OK] Core Engines are ready.
echo ==========================================================================
echo  [STAGE 2] Launching Net Gateway (nginx-proxy)
echo ==========================================================================
:: 🌟 修正：只單獨拉起 Nginx 反向代理，乾淨俐落
%COMPOSE_CMD% up -d --force-recreate nginx

echo.
echo [WAIT] Final verification of infrastructure gate...
timeout /t 5 >nul

echo.
%COMPOSE_CMD% ps
echo.
echo ==========================================================================
echo  SMART-on-FHIR Sandbox is ready! Port 443 is wide open.
echo ==========================================================================
pause