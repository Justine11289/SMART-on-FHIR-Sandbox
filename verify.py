import urllib.parse
import urllib.request
import urllib.error
import json
import base64
import os
import uuid
import ssl
import sys

# ==================== Sandbox Global Configurations ====================
BASE_URL = os.environ.get("VERIFY_BASE_URL", "https://smartonfhir.sandbox.local")
KEYCLOAK_REALM = os.environ.get("VERIFY_KEYCLOAK_REALM", "fhir")
KEYCLOAK_ADMIN_REALM = os.environ.get("VERIFY_KEYCLOAK_ADMIN_REALM", "master")
KEYCLOAK_ADMIN_CLIENT_ID = os.environ.get("VERIFY_KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli")
KEYCLOAK_ADMIN_USERNAME = os.environ.get("VERIFY_KEYCLOAK_ADMIN_USERNAME", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.environ.get("VERIFY_KEYCLOAK_ADMIN_PASSWORD", "admin")
KEYCLOAK_CALLBACK_URI = os.environ.get(
    "VERIFY_KEYCLOAK_CALLBACK_URI", f"{BASE_URL}/v/r4/auth/keycloak-callback"
)

REQUESTED_SCOPES = [
    "launch",
    "launch/patient",
    "patient/*.read",
    "fhirUser",
    "online_access",
    "openid",
]

SSL_CONTEXT = ssl._create_unverified_context()


def base64url_encode(text: str) -> str:
    encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def http_request(*, method: str, url: str, headers: dict | None = None, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, context=SSL_CONTEXT) as response:
            body = response.read().decode("utf-8")
            return response.status, body, dict(response.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, body, dict(exc.headers)


def get_keycloak_admin_token() -> str:
    token_url = f"{BASE_URL}/realms/{KEYCLOAK_ADMIN_REALM}/protocol/openid-connect/token"
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": KEYCLOAK_ADMIN_CLIENT_ID,
            "username": KEYCLOAK_ADMIN_USERNAME,
            "password": KEYCLOAK_ADMIN_PASSWORD,
        }
    ).encode("utf-8")

    status, body, _ = http_request(
        method="POST",
        url=token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=form,
    )

    if status != 200:
        raise RuntimeError(f"Keycloak admin token request failed ({status}): {body}")

    payload = json.loads(body)
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Keycloak admin token response did not include access_token")

    return token


def keycloak_api(*, method: str, path: str, token: str, payload: dict | None = None):
    url = f"{BASE_URL}/admin/realms/{KEYCLOAK_REALM}{path}"
    data = None
    headers = {"Authorization": f"Bearer {token}"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    return http_request(method=method, url=url, headers=headers, data=data)


def ensure_client_scope(token: str, scope_name: str) -> None:
    status, body, _ = keycloak_api(
        method="POST",
        path="/client-scopes",
        token=token,
        payload={"name": scope_name, "protocol": "openid-connect"},
    )

    if status not in (201, 409):
        raise RuntimeError(f"Failed to create Keycloak client scope '{scope_name}' ({status}): {body}")


def find_client_scope_id(token: str, scope_name: str) -> str:
    status, body, _ = keycloak_api(method="GET", path="/client-scopes", token=token)
    if status != 200:
        raise RuntimeError(f"Failed to list Keycloak client scopes ({status}): {body}")

    scopes = json.loads(body)
    for scope in scopes:
        if scope.get("name") == scope_name:
            scope_id = scope.get("id")
            if scope_id:
                return scope_id

    raise RuntimeError(f"Could not find Keycloak client scope id for '{scope_name}'")


def create_client(token: str, *, client_id: str, redirect_uri: str) -> str:
    redirect_uris = [redirect_uri]
    if KEYCLOAK_CALLBACK_URI not in redirect_uris:
        redirect_uris.append(KEYCLOAK_CALLBACK_URI)

    status, body, headers = keycloak_api(
        method="POST",
        path="/clients",
        token=token,
        payload={
            "clientId": client_id,
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": True,
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "implicitFlowEnabled": False,
            "authorizationServicesEnabled": False,
            "fullScopeAllowed": True,
            "redirectUris": redirect_uris,
            "webOrigins": ["*"],
        },
    )

    if status not in (201, 204, 409):
        raise RuntimeError(f"Failed to create Keycloak client '{client_id}' ({status}): {body}")

    location = headers.get("Location") or headers.get("location")
    if location and "/clients/" in location:
        return location.rsplit("/", 1)[-1]

    status, body, _ = keycloak_api(method="GET", path=f"/clients?clientId={urllib.parse.quote(client_id)}", token=token)
    if status != 200:
        raise RuntimeError(f"Failed to resolve Keycloak client id for '{client_id}' ({status}): {body}")

    clients = json.loads(body)
    if not clients:
        raise RuntimeError(f"Keycloak did not return a client for '{client_id}'")

    client_uuid = clients[0].get("id")
    if not client_uuid:
        raise RuntimeError(f"Keycloak client '{client_id}' did not include an internal id")
    return client_uuid


def attach_default_scope(token: str, client_uuid: str, scope_uuid: str, scope_name: str) -> None:
    status, body, _ = keycloak_api(
        method="PUT",
        path=f"/clients/{client_uuid}/default-client-scopes/{scope_uuid}",
        token=token,
    )
    if status not in (204, 201, 409):
        raise RuntimeError(f"Failed to attach default scope '{scope_name}' ({status}): {body}")


def register_with_keycloak(*, client_id: str, redirect_uri: str) -> None:
    token = get_keycloak_admin_token()

    for scope_name in REQUESTED_SCOPES:
        ensure_client_scope(token, scope_name)

    client_uuid = create_client(token, client_id=client_id, redirect_uri=redirect_uri)

    for scope_name in REQUESTED_SCOPES:
        scope_uuid = find_client_scope_id(token, scope_name)
        attach_default_scope(token, client_uuid, scope_uuid, scope_name)

    print(f"Already registered client with Keycloak：{client_id}")


def encode_launch_params(*, client_id: str, redirect_uri: str) -> str:
    # Matches smart-launcher-v2/src/isomorphic/codec.ts for provider-ehr launch.
    launch_params = [
        0,              # provider-ehr
        "",            # patient
        "",            # provider
        "AUTO",        # encounter
        0,              # skip_login
        0,              # skip_auth
        0,              # sim_ehr
        "",            # scope
        redirect_uri,    # redirect_uris
        client_id,       # client_id
        "",            # client_secret
        "",            # auth_error
        "",            # jwks_url
        "",            # jwks
        0,              # client_type -> public
        1,              # pkce -> auto
        ""             # fhir_server
    ]

    return base64url_encode(json.dumps(launch_params, separators=(",", ":")))


def build_launcher_url(*, app_url: str, redirect_uri: str, client_id: str, fhir_version: str = "r4") -> str:
    launch = encode_launch_params(client_id=client_id, redirect_uri=redirect_uri)
    query = urllib.parse.urlencode(
        {
            "fhir_version": fhir_version,
            "launch_url": app_url,
            "launch": launch,
        },
        quote_via=urllib.parse.quote,
    )
    return f"{BASE_URL}/?{query}"


def run_session():
       
    app_url = input("App Launch URL: ").strip()
    redirect_uri = input("Redirect URI: ").strip()
    client_id = str(uuid.uuid4())
    
    if not app_url or not redirect_uri:
        print("Error：URL can't be empty！")
        return

    try:
        register_with_keycloak(client_id=client_id, redirect_uri=redirect_uri)
    except Exception as exc:
        print(f"Keycloak registration failed：{exc}")
        sys.exit(1)

    launcher_url = build_launcher_url(app_url=app_url, redirect_uri=redirect_uri, client_id=client_id)

    print(f"="*80)
    print("SMART Launcher URL：")
    print(f"\033[92m{launcher_url}\033[0m")
    print(f"="*80)
    
    input("Press Enter to exit...")

if __name__ == "__main__":
    run_session()