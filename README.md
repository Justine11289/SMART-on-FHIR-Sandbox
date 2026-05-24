# SMART on FHIR Sandbox



This repository packages together:

- a SMART launcher frontend and backend
- a Keycloak realm for authentication and OAuth2/OIDC flows
- an R4 HAPI FHIR server
- a patient browser for sample data
- an Nginx reverse proxy that serves the sandbox over HTTP or HTTPS

This sandbox is for development and testing only. It is not intended for clinical use and should not be used to store or access real patient data.

## What this project is for

Use this sandbox when you want to:

- test a SMART on FHIR app locally
- validate a launch flow against Keycloak
- register a fresh client id for each test run with `verify.py`
- test an external app hosted on GitHub Pages or another HTTPS origin
- confirm an app can pass the sandbox CSP and redirect restrictions

## Repository layout

- `docker-compose.yml` - main sandbox stack definition
- `nginx.conf` - reverse proxy and Content Security Policy configuration
- `verify.py` - helper script that registers a client in Keycloak and generates a SMART launcher URL
- `smart-launcher-v2/` - SMART launcher application and backend
- `patient-browser/` - sample patient browser configuration
- `keycloak-data/` - imported realm configuration
- `certs/` - local TLS certificate files used in HTTPS mode
- `start_sandbox.bat` - Windows helper script for HTTPS startup
- `start_fixed_host.bat` - helper script for fixed host deployment
- `www/` - static landing pages and templates

## Services

The default stack includes these services:

- `nginx` - public entry point and TLS termination
- `keycloak` - authentication server and realm import
- `smart-launcher` - SMART launch orchestration and OAuth flow handling
- `r4` - HAPI FHIR R4 server
- `patient-browser` - sample data browser UI
- `db` - PostgreSQL database for Keycloak

## Requirements

You need:

- Docker Desktop or another Docker Engine compatible runtime
- Docker Compose v2
- Git
- A modern browser
- Node.js if you want to update patient-browser autocomplete data

Recommended system memory:

- at least 4 GB if you run the full sandbox stack
- more if you enable multiple services or larger FHIR datasets

## Quick start

### 1. Clone the repository

```sh
git clone https://github.com/smart-on-fhir/smart-dev-sandbox.git
cd smart-dev-sandbox
```

### 2. Start the sandbox

```sh
docker compose up -d
```

### 3. Open the sandbox

- HTTP mode: `http://localhost`
- HTTPS mode: `https://smartonfhir.sandbox.local` or the host configured in `.env`

If you are using the HTTPS startup script on Windows, open the generated public host instead of `localhost`.

## Configuration

The sandbox reads its configuration from `.env` and from environment variables passed through `docker compose`.

Important settings include:

- `PUBLIC_HOST` - public host name used by launcher, Keycloak, and generated URLs
- `HOST` - local host binding for non-HTTPS workflows
- `LAUNCHER_SECRET` - signing secret used by the SMART launcher
- `KEYCLOAK_ADMIN` - Keycloak admin user for bootstrap and admin API access
- `KEYCLOAK_ADMIN_PASSWORD` - Keycloak admin password
- `KC_BOOTSTRAP_ADMIN_USERNAME` - bootstrap admin username during first realm start
- `KC_BOOTSTRAP_ADMIN_PASSWORD` - bootstrap admin password during first realm start
- `CLIENT_ID` - FHIR client id used by the sandbox itself
- `R4_IMAGE` - R4 HAPI image tag

After changing `.env`, restart the stack:

```sh
docker compose down
docker compose up -d
```

## HTTPS mode for external SMART apps

If you want to test an app hosted on another HTTPS origin, use the HTTPS mode and the generated sandbox certificate.

On Windows, start the sandbox with:

```bat
start_sandbox.bat
```

What this does:

- detects your LAN IP
- updates `.env`
- reuses or creates TLS files in `./certs`
- starts the stack behind HTTPS

### Fixed host mode

If you want a stable host name such as `smartonfhir.sandbox.local`, use the fixed host helper:

```bat
start_fixed_host.bat
```

This is useful when your test app has a fixed CSP or when you want a predictable redirect URI during repeated tests.

## How to test an external SMART app

The app you are testing must match the sandbox launch expectations.

### Required app format

Your test app should:

- be served from an HTTPS origin
- expose a stable launch page or landing page URL
- accept SMART launch query parameters or handle a redirect from the SMART launcher
- use a redirect URI that is registered in Keycloak for that test client
- keep the redirect URI exact, including scheme, host, path, and trailing slash rules
- avoid relying on `localhost` when the sandbox is running on a public host name

A typical test app flow is:

1. Open `verify.py`
2. Provide the app launch URL
3. Provide the final redirect URI
4. Use the generated SMART launcher URL
5. Complete login and authorization in Keycloak
6. Return to your app through the registered redirect URI

### CSP requirements

The sandbox sets a restrictive Content Security Policy in `nginx.conf` for the public sandbox origin.

The important rule for test apps is the `connect-src` policy. The sandbox allows requests only to:

- `'self'`
- `https://<sandbox-host>`
- `https://*.smarthealthit.org`
- `https://cdn.jsdelivr.net`

In practice this means your test app must either:

- already allow `https://smartonfhir.sandbox.local` in its own CSP, or
- be deployed on a host whose CSP is already compatible with the sandbox origin, or
- be modified to include the sandbox origin in `connect-src`

If your app performs fetch/XHR calls to the sandbox FHIR endpoint, those requests must be permitted by the app’s own CSP as well as the sandbox’s CSP.

### Common CSP problems

Typical failures include:

- the app blocks fetch/XHR to `https://smartonfhir.sandbox.local`
- the app hardcodes a different launch host in its CSP allowlist
- the app uses HTTP while the sandbox is running over HTTPS
- the app’s `redirect_uri` does not exactly match the Keycloak client configuration

### Example app compatibility checklist

Before testing an app, confirm:

- the app page is available over HTTPS
- the app’s CSP includes the sandbox host in `connect-src` if it makes calls to the sandbox
- the launch URL is reachable from the browser
- the final redirect URI is registered in Keycloak
- the app can survive being launched with SMART query parameters such as `launch_url`, `launch`, `fhir_version`, and `state`
- the app does not depend on a stale `client_secret` in local storage

## Using `verify.py`

`verify.py` is the easiest way to generate a fresh launch URL for testing.

It will:

- read the app launch URL from stdin
- read the redirect URI from stdin
- create a fresh client id in Keycloak
- create and attach the SMART scopes needed for the launch
- register both the app redirect URI and the launcher callback URI
- print a SMART launcher URL you can open in the browser

Example:

```sh
python verify.py
```

You will be prompted for:

- App Launch URL
- Redirect URI

The script then prints a launcher URL similar to:

```text
https://smartonfhir.sandbox.local/?fhir_version=r4&launch_url=...
```

### Keycloak registration behavior

Each run creates a fresh client id and registers:

- the app redirect URI you entered
- `https://<sandbox-host>/v/r4/auth/keycloak-callback`

It also creates or reuses these SMART client scopes:

- `launch`
- `launch/patient`
- `patient/*.read`
- `openid`
- `fhirUser`
- `online_access`

## Launch flow

The general SMART on FHIR flow in this sandbox is:

1. Open the launcher URL generated by `verify.py`
2. The launcher redirects to Keycloak
3. The user logs in with Keycloak credentials
4. The launcher continues the SMART flow
5. The app receives the final code-based redirect
6. The app exchanges the code for a token through the sandbox token endpoint

For the current sandbox configuration, practitioner login happens before patient selection.

## Patient browser configuration

If you add or update sample patient data, regenerate the patient browser condition data:

```sh
cd patient-browser
npm i
node sync-conditions.js -s 4
cd ..
docker compose down
docker compose up -d
```

Use `-s 2`, `-s 3`, or `-s 4` depending on the FHIR version you are updating.

## FHIR data

The HAPI FHIR R4 server is preloaded with sample data and persists in a Docker volume.

If you switch the database image or want to reset the data, remove the relevant container and volume first.

Example:

```sh
docker container rm hapi-r4
docker volume rm smart-dev-sandbox_r4-database
```

Then restart the sandbox with `docker compose up -d`.

## Running with a stable public host

If you need a long-lived host name for integration tests, set the public host in `.env` and use the fixed host startup path.

This is useful when:

- your external app CSP is host-specific
- you want stable OAuth redirect URIs
- you need predictable URLs for automated tests

## Troubleshooting

### `Invalid parameter: redirect_uri`

This usually means the redirect URI used by the app is not exactly registered in Keycloak.

Check that:

- the URI matches character-for-character
- the scheme is correct (`https` vs `http`)
- the host is correct
- the path matches exactly
- trailing slashes are consistent

### `invalid_grant: Code not valid`

This usually means one of the following:

- the code was already used once
- the code expired
- the code was issued for a different redirect URI
- the browser session was stale and reused an old redirect

### CSP or network errors in the browser

If your app cannot fetch from the sandbox:

- verify the app’s own CSP includes the sandbox origin
- verify the sandbox is running on the expected host
- verify the browser trusts the sandbox certificate when using HTTPS mode
- make sure the app uses HTTPS everywhere

### Keycloak login appears to work but redirect fails

Check:

- the Keycloak client has the correct redirect URIs
- the launcher callback URI is present
- the test app uses the same redirect URI that was registered by `verify.py`

## Security notes

- This sandbox uses self-signed certificates in local HTTPS mode unless you provide your own TLS files.
- Do not use production credentials or production patient data here.
- Keep admin credentials out of source control in real deployments.
- If your test app stores OAuth tokens or client secrets in local storage, clear stale values before testing a new launch.

