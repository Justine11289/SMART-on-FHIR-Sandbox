@echo off
setlocal enabledelayedexpansion

:: ======================================================
:: Step 0: Check for Administrator Privileges
:: ======================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Requesting administrator privileges...
    powershell start-process -FilePath '%0' -Verb runas
    exit /b
)

:: CRITICAL: Fix working directory to project folder
cd /d "%~dp0"

:: ======================================================
:: Step 1: Automatic Hosts Configuration (Local Domain)
:: ======================================================
set "HOSTS_FILE=%SystemRoot%\System32\drivers\etc\hosts"
set "DOMAINS=fhir.sandbox.local auth.authorize.sandbox.local"

echo [INFO] Current Directory: %CD%
echo [INFO] Validating DNS settings in Hosts file...

for %%D in (%DOMAINS%) do (
    findstr /i /c:"%%D" "%HOSTS_FILE%" >nul
    if !errorlevel! neq 0 (
        echo [ADD] Mapping 127.0.0.1 to %%D...
        echo 127.0.0.1 %%D >> "%HOSTS_FILE%"
    ) else (
        echo [OK] %%D is correctly mapped.
    )
)

:: ======================================================
:: Step 2: Set Core Environment Variables
:: ======================================================
set "SANDBOX_PUBLIC_HOST=fhir.sandbox.local"
set "SANDBOX_USE_EXISTING_CERT=1"

echo.
echo [INFO] Fixed-host mode: Enabled
echo [INFO] Target Domain: %SANDBOX_PUBLIC_HOST%
echo.

:: Call the main sandbox startup script
call ".\start_sandbox.bat"