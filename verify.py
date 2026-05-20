import requests
import uuid
import urllib.parse
import json
import base64

# ==================== Sandbox Global Configurations ====================
BASE_URL = "https://fhir.sandbox.local"
TARGET_REALM = "fhir"  
ADMIN_USER = "admin"
ADMIN_PASS = "admin"

requests.packages.urllib3.disable_warnings()

def get_admin_token():
    url = f"{BASE_URL}/realms/master/protocol/openid-connect/token"
    payload = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASS
    }
    response = requests.post(url, data=payload, verify=False)
    if response.status_code != 200:
        raise Exception(f"Keycloak Master Authentication Failed: {response.text}")
    return response.json().get("access_token")

def run_session():
    print("==========================================================================")
    print(" SMART-on-FHIR 正統醫院流派：獨立發動連接器 (Pure Standalone Mode)")
    print("==========================================================================")
    
    app_url = input("Enter App Launch.html URL: ").strip()
    redirect_uri = input("Enter Redirect URI (index.html): ").strip()

    try:
        token = get_admin_token()
    except Exception as e:
        print(f"\n❌ Connection Error: {e}")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    reg_url = f"{BASE_URL}/admin/realms/{TARGET_REALM}/clients"
    
    test_id = str(uuid.uuid4())
    
    # 建立純粹的 OAuth2 Public Client
    client_payload = {
        "clientId": test_id,
        "enabled": True,
        "publicClient": True,                   
        "bearerOnly": False,
        "standardFlowEnabled": True,            
        "directAccessGrantsEnabled": True,
        "redirectUris": [
            f"{redirect_uri}*",                           
            f"{BASE_URL}*",                            
            f"{app_url}*"
        ],
        "webOrigins": ["*"]                     
    }
    
    reg_res = requests.post(reg_url, json=client_payload, headers=headers, verify=False)
    if reg_res.status_code != 201:
        print(f"\n❌ Client Registration Failed: {reg_res.text}")
        return

    # 雙重鎖定 Public Client 屬性
    internal_query = requests.get(f"{reg_url}?clientId={test_id}", headers=headers, verify=False).json()
    internal_id = internal_query[0]['id']
    full_config = internal_query[0]
    full_config["standardFlowEnabled"] = True
    full_config["publicClient"] = True
    full_config["grantTypes"] = ["authorization_code", "refresh_token"]
    requests.put(f"{reg_url}/{internal_id}", json=full_config, headers=headers, verify=False)

    print(f"\n[OK] 臨時 Public Client {test_id} 已成功註冊至 Keycloak 核心。")

    # 🌟 正統關鍵：直接把發動目標（iss）指向真正受到 Keycloak 保護的 HAPI-FHIR 門牌！
    # 這樣妳的 App 就會直接去讀取 HAPI-FHIR 的 smart-configuration，進而直衝 Keycloak 大門！
    real_fhir_server = f"{BASE_URL}/fhir/hapi-fhir-jpaserver/fhir"
    
    params = urllib.parse.urlencode({
        "iss": real_fhir_server,
        "clientId": test_id
    })
    
    print(f"\n🚀 正統醫院流派發動連結已就緒 (完全繞過 smart-launcher 雜音)：")
    print(f"\n\033[94m{app_url}?{params}\033[0m")
    
    print("\n" + "-"*60)
    input("👉 請【複製上方藍色連結】，並打開【瀏覽器無痕視窗】貼上。測試完成後在此按 [ENTER] 銷毀 Session...")
    
    requests.delete(f"{reg_url}/{internal_id}", headers=headers, verify=False)
    print(f"\n✅ 測試結束。Client {test_id} 已從 Keycloak 安全下線清空。")

if __name__ == "__main__":
    run_session()