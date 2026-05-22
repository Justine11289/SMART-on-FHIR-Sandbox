#!/usr/bin/env python3
import os, sys, json, uuid, re
from urllib.parse import urlencode, urljoin, urlparse, parse_qs
import ssl
import urllib.request
import urllib.error

import requests

# Load config from env or .env
BASE_URL = os.environ.get('VERIFY_BASE_URL') or os.environ.get('PUBLIC_HOST') or 'https://smartonfhir.sandbox.local'
KEYCLOAK_REALM = os.environ.get('VERIFY_KEYCLOAK_REALM', 'fhir')
KC_ADMIN_REALM = os.environ.get('VERIFY_KEYCLOAK_ADMIN_REALM', 'master')
KC_ADMIN_CLIENT = os.environ.get('VERIFY_KEYCLOAK_ADMIN_CLIENT_ID', 'admin-cli')
KC_ADMIN_USER = os.environ.get('VERIFY_KEYCLOAK_ADMIN_USERNAME') or os.environ.get('KEYCLOAK_ADMIN') or 'admin'
KC_ADMIN_PASS = os.environ.get('VERIFY_KEYCLOAK_ADMIN_PASSWORD') or os.environ.get('KEYCLOAK_ADMIN_PASSWORD') or 'admin'

APP_URL = sys.argv[1] if len(sys.argv) > 1 else 'https://justine11289.github.io/Clinical-Decision-Calculator-Platform/index.html'
REDIRECT_URI = sys.argv[2] if len(sys.argv) > 2 else APP_URL

SCOPES = 'launch launch/patient patient/*.read openid fhirUser online_access'

session = requests.Session()
session.verify = False

def get_admin_token():
    token_url = f"{BASE_URL}/realms/{KC_ADMIN_REALM}/protocol/openid-connect/token"
    r = session.post(token_url, data={
        'grant_type': 'password',
        'client_id': KC_ADMIN_CLIENT,
        'username': KC_ADMIN_USER,
        'password': KC_ADMIN_PASS
    })
    r.raise_for_status()
    return r.json()['access_token']

def kc_api(method, path, token, json_payload=None, params=None):
    url = f"{BASE_URL}/admin/realms/{KEYCLOAK_REALM}{path}"
    headers = {'Authorization': f'Bearer {token}'}
    if json_payload is not None:
        r = session.request(method, url, headers=headers, json=json_payload, params=params, allow_redirects=False)
    else:
        r = session.request(method, url, headers=headers, params=params, allow_redirects=False)
    return r


def ensure_scope(token, name):
    r = kc_api('POST', '/client-scopes', token, json_payload={'name': name, 'protocol': 'openid-connect'})
    if r.status_code not in (201, 409):
        raise RuntimeError(f'Failed to create scope {name}: {r.status_code} {r.text}')

def get_scope_id(token, name):
    r = kc_api('GET', '/client-scopes', token)
    r.raise_for_status()
    for s in r.json():
        if s.get('name') == name:
            return s.get('id')
    raise RuntimeError('scope id not found')

def create_client(token, client_id, redirect_uri):
    payload = {
        'clientId': client_id,
        'enabled': True,
        'protocol': 'openid-connect',
        'publicClient': True,
        'standardFlowEnabled': True,
        'redirectUris': [redirect_uri],
        'webOrigins': ['*'],
        'fullScopeAllowed': True
    }
    r = kc_api('POST', '/clients', token, json_payload=payload)
    if r.status_code not in (201, 409):
        raise RuntimeError(f'Failed create client: {r.status_code} {r.text}')
    # find id
    r2 = kc_api('GET', '/clients', token, None, params={'clientId': client_id})
    r2.raise_for_status()
    data = r2.json()
    if not data:
        raise RuntimeError('client not found after create')
    return data[0]['id']


def attach_default_scope(token, client_uuid, scope_uuid):
    r = kc_api('PUT', f'/clients/{client_uuid}/default-client-scopes/{scope_uuid}', token)
    if r.status_code not in (204, 201, 409):
        raise RuntimeError(f'attach scope failed: {r.status_code} {r.text}')


def simulate_login(client_id, redirect_uri):
    auth_url = f"{BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': SCOPES,
        'state': 'test-state',
        'aud': f'{BASE_URL}/v/r4/fhir'
    }
    r = session.get(auth_url, params=params, allow_redirects=False)
    print('AUTH status', r.status_code)
    html = r.text
    m = re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', html)
    if not m:
        print('Login form not found; response excerpt:')
        print(html[:800])
        return None
    action = m.group(1)
    form_url = urljoin(r.url, action)
    inputs = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html))
    # set creds
    username = os.environ.get('KC_BOOTSTRAP_ADMIN_USERNAME') or os.environ.get('KEYCLOAK_ADMIN') or 'fhir-admin'
    password = os.environ.get('KC_BOOTSTRAP_ADMIN_PASSWORD') or os.environ.get('KEYCLOAK_ADMIN_PASSWORD') or 'pa55word'
    inputs['username'] = username
    inputs['password'] = password
    post = session.post(form_url, data=inputs, allow_redirects=False)
    print('POST status', post.status_code)
    loc = post.headers.get('Location')
    print('POST Location:', loc)
    # follow if redirect to redirect_uri
    if loc and redirect_uri in loc:
        print('Final redirect to app:', loc)
        parsed = urlparse(loc)
        qs = parse_qs(parsed.query)
        print('Query params:', qs)
        return loc
    # else follow next
    if loc:
        r2 = session.get(loc, allow_redirects=False)
        print('Next status', r2.status_code)
        print('Next Location', r2.headers.get('Location'))
        if r2.headers.get('Location') and redirect_uri in r2.headers.get('Location'):
            print('Final redirect to app:', r2.headers.get('Location'))
            return r2.headers.get('Location')
    return None


def main():
    token = get_admin_token()
    client_id = str(uuid.uuid4())
    print('Registering client', client_id)
    # ensure scopes
    for scope in ['launch','launch/patient','patient/*.read','fhirUser','openid','online_access']:
        try:
            ensure_scope(token, scope)
        except Exception as e:
            print('scope ensure:', e)
    client_uuid = create_client(token, client_id, REDIRECT_URI)
    print('client uuid', client_uuid)
    for scope in ['launch','launch/patient','patient/*.read','fhirUser','openid']:
        try:
            sid = get_scope_id(token, scope)
            attach_default_scope(token, client_uuid, sid)
        except Exception as e:
            print('attach scope', scope, e)
    # simulate login
    final = simulate_login(client_id, REDIRECT_URI)
    if final:
        print('SUCCESS: final redirect ->', final)
    else:
        print('Flow did not reach redirect to app')

if __name__=='__main__':
    main()
