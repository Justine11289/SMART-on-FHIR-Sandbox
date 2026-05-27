# SMART on FHIR Sandbox

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-brightgreen.svg)]()
[![FHIR R4](https://img.shields.io/badge/FHIR-R4-orange.svg)](https://www.hl7.org/fhir/resourcelist.html)
[![Keycloak](https://img.shields.io/badge/Keycloak-24.x-lightgrey.svg)](https://www.keycloak.org/)

An enterprise-grade, containerized orchestration platform engineered to simulate a production-ready **SMART on FHIR (HL7 R4)** environment. This sandbox provides healthcare software engineers, hospital IT departments, and clinical researchers with a high-fidelity, localized ecosystem to validate and stress-test digital health applications under rigid HTTPS security topologies, OAuth 2.0 / OpenID Connect (OIDC) protocols, and stringent Content Security Policies (CSP).

> ### ⚠️ Regulatory & Safety Compliance Notice
> This platform is designated strictly for pre-clinical software verification, integration testing, and academic validation. It does not possess medical device clearance (e.g., TFDA/FDA SaMD), lacks production-grade access controls, and **must never** be deployed to process, store, or transmit real Protected Health Information (PHI) or actual clinical datasets.

---

## Technical Architecture
The platform does not merely run these microservices in parallel. Instead, it orchestrates a tightly coupled, federated security architecture governed by the **HL7 SMART App Launch Protocol** and **OAuth 2.0 / OIDC specifications**. 
### System Architecture
The system topology establishes a critical trust triangle between the Identity Provider (Keycloak), the Context Launcher, and the Protected Resource Server (HAPI FHIR R4). All intra-container token introspections and context bindings are executed within an isolated Docker virtual network, exposing only unified encrypted endpoints to the host system.

```text
 ┌────────────────────────┐
 │     smart-launcher     │ (1) Ingests Launch Request & Generates Context
 └───────────┬────────────┘
             │ 
             │ (2) Redirects for Authentication via Nginx Proxy
             ▼
 ┌────────────────────────┐
 │        keycloak        │ (3) Validates Practitioner Identity 
 │   (Identity Provider)  │ (4) Mints Cryptographically Signed Access Tokens
 └───────────┬────────────┘
             │
             │ (5) Presents Access Token with SMART Scopes (e.g., patient/*.read)
             ▼
 ┌────────────────────────┐
 │     HAPI FHIR R4       │ (6) Introspects/Verifies Token Signature against Keycloak
 │   (Resource Server)    │ (7) Releases Authorized Clinical Profiles (Demographics/Vitals)
 └────────────────────────┘
```
### Service Architecture
- Contextual Orchestration (smart-launcher): Rather than acting as a standalone web application, it simulates the Electronic Health Record (EHR) session state. It initializes the launch handshake by binding user sessions to specific clinical contexts (Patient ID / Practitioner ID) before federating the authorization request.
- Identity Federation & Access Control (keycloak / db): Serving as the centralized Authorization Server backed by a dedicated PostgreSQL volume, it ingests requests from the launcher. It manages OAuth 2.0 client registries configured via verify.py and enforces role-based access control, translating clinician identities into cryptographically secure JSON Web Tokens (JWT).
- Protected Resource Server (r4): The HAPI FHIR engine operates under explicit token-verification constraints. It does not expose clinical endpoints openly; instead, it intercepts all incoming RESTful HTTP requests, cross-references the embedded OAuth 2.0 bearer tokens against Keycloak's public keys, and enforces scope-level data filtering.
- Edge Proxy Gatekeeper (nginx / certs): Wraps all interconnected components behind a unified TLS 1.3 reverse-proxy. This ensures that token exchanges, launch contexts, and FHIR resource queries are encrypted under a monolithic host interface to satisfy identical cross-origin policies and mitigate mixed-content vulnerabilities.
#### Key Features
- High-Fidelity HTTPS Simulation: Implements an automated local Certificate Authority (CA) pipeline. Generates dynamic TLS credentials to test external applications hosted on public secure origins under realistic browser runtime constraints.
- Dynamic Client Provisioning Engine: A programmatic onboarding utility that communicates with Keycloak's Administration API to register fresh clients on-the-fly, automating the mapping of complex SMART OAuth scopes without manual dashboard configuration.
- Rigid CSP Emulation: Pre-configured with restrictive HTTP header rules within Nginx to flag cross-origin errors, mixed-content blocks, and unauthorized socket connections prior to hospital-wide EHR deployment.
### Directory Structure
```
├── docker-compose.yml       # Multi-container orchestration blueprint
├── nginx.conf               # Enterprise reverse-proxy & rigid CSP layout
├── verify.py                # Keycloak API client onboarding & launch URL generator
├── smart-launcher-v2/       # Core SMART launch handler and backend services
├── patient-browser/         # UI subsystem for cohort identification and lookup
├── keycloak-data/           # Pre-configured medical realm configurations
├── certs/                   # Automated storage for local TLS certificate chains
├── start_sandbox.bat        # Automated initialization script for dynamic LAN environments
└── start_fixed_host.bat     # Automated initialization script for static hostname mapping
```

## Deployment
### Prerequisites
- Docker Desktop v24.0+ / Docker Engine compatible runtime
- Docker Compose v2.0+
- Python 3.8+ (with `requests` library for client registration scripts)
1. Protocol A: Stable Host Deployment (Recommended)

   For long-lived integration pipelines, deterministic OAuth redirect URIs, and rigid app-side CSP definitions, bind the platform to a fixed loopback domain (`https://smartonfhir.sandbox.local`):
   ```bash
   start_fixed_host.bat
   ```
3. Protocol B: Dynamic LAN Topology Deployment
   To perform point-of-care verification using external devices within the same local network, utilize the dynamic IP auto-detection pipeline:
   ```bash
   start_sandbox.bat
   ```
 
 _This script automatically resolves your current active IPv4 interface, provisions matching TLS certificates, and updates the core ecosystem configuration dynamically._

### Core Environment Schema (`.env`)
The orchestration runtime depends on the following localized environmental parameters:
- `PUBLIC_HOST`: The canonical secure FQDN or IP interface parsed by the authorization server.
- `LAUNCHER_SECRET`: A high-entropy cryptographic seed used to sign state tokens during authorization handshakes.

### SMART App Integration Specification
External digital health solutions attempting to interface with this sandbox must comply with the following technical interface specifications:
1. OAuth 2.0 Client Registration via `verify.py`

   Invoke the automated registration script within your continuous integration console:
   ```bash
   python verify.py
   ```
   The script requires execution parameters passed through standard input:
   - App Launch URL: The exact secure HTTPS route of your application's launch landing page.
   - Redirect URI: The absolute, case-sensitive callback endpoint authorized to exchange authorization codes for access tokens.

2. Authorization Scopes

   The platform provisions access tokens embedded with standard HL7 SMART App Launch scopes, including but not limited to:
   - `launch` & `launch/patient`: Contextual execution authorization within an active record.
   - `patient/*.read`: Read-level granularity across all preloaded FHIR resources.
   - `openid` & `fhirUser`: Cross-entity identity verification.

3. Network Layer Security & CSP Whitelisting

   To prevent browser-level network drops, client applications executing fetch/XHR calls to the FHIR repository must whitelist the sandbox edge domain inside their native Content Security Policy headers:
   ```HTTP
   Content-Security-Policy: connect-src 'self' [https://smartonfhir.sandbox.local](https://smartonfhir.sandbox.local);
   ```

## Troubleshooting
1. `Invalid parameter: redirect_uri`
   - Root Cause: The authorization request issued by the client application does not match the character string registered inside Keycloak via `verify.py`.
   - Resolution: Verify that protocol schemes (`https`), hostnames, port sub-strings, and trailing slashes (`/`) match identically across both configurations.
2. `invalid_grant: Code not valid`
   - Root Cause: Reutilization of an expired authorization code or mismatch in client credentials during the POST exchange.
   - Resolution: Re-initiate the launch workflow sequence from the primary launcher URL to obtain an unspent authorization grant.
5. TLS / Untrusted Authority Exceptions
   - Root Cause: Modern web browsers block connection requests to self-signed TLS endpoints by default.
   - Resolution: Manually import the root certificate generated in the `./certs` repository into your system's trust store, or explicitly bypass the security exception inside the local testing browser profile.

## Scalability Targets
- Multi-Version Coexistence: Extending orchestration bindings to support concurrent FHIR R5 architectures alongside existing R4 profiles.
- Regional Guide Profiles: Incorporating specific regional implementation guide validations, specifically targeting Taiwan Core Implementation Guide (TW Core IG) structural definitions.
- Synthetic Generation Pipelines: Integrating automated synthesis tools to refresh clinical test data dynamically upon network initializations.

## Credits, Governance & License
- Platform & Security Engineering: Tzu-Ting Huang and Chang Gung Memorial Hospital (CGMH).
- Upstream Blueprint Attribution: Portions of this platform's architecture, launch workflow orchestration, and core components are derived from the open-source [SMART Launcher v2](https://github.com/smart-on-fhir/smart-launcher-v2) (Copyright © Boston Children's Hospital)
- Enforced Industry Standards: HL7 FHIR Standard (v4.0.1), SMART App Launch Framework (v2.0.0), OAuth 2.0 (RFC 6749), OpenID Connect Core 1.0.
- License: Distributed under the terms of the MIT License.

Copyright © 2026 Tzu-Ting Huang, CGMH. All rights reserved.
   

